# Questões sobre o Algoritmo Raft

## 1. Quais são os principais desafios de controle de concorrência no Raft?

O Raft opera em um ambiente distribuído onde múltiplos nós executam simultaneamente e se comunicam via RPC, o que introduz diversos desafios de concorrência:

- **Acesso concorrente ao estado do nó**: o estado de cada nó (termo, `voted_for`, log, `commit_index`, estado atual) pode ser acessado simultaneamente pela thread do tick loop (que verifica timeouts e dispara eleições) e pelas threads que tratam RPCs recebidos (`request_vote`, `append_entries`). Sem sincronização adequada (como um `threading.Lock`), leituras e escritas simultâneas podem corromper o estado. Na nossa implementação, o `RaftNodeProxy` utiliza um lock global (`self.lock`) que protege todo acesso ao `RaftNode`.

- **Eleições concorrentes (split vote)**: dois ou mais nós podem iniciar eleições no mesmo termo simultaneamente, dividindo os votos. O Raft mitiga isso com **timeouts de eleição aleatórios** (no nosso caso, entre 5 e 30 segundos), reduzindo a probabilidade de colisão. Ainda assim, split votes podem ocorrer e o algoritmo simplesmente aguarda um novo timeout para tentar novamente.

- **Replicação paralela para múltiplos followers**: o líder envia `AppendEntries` para todos os followers em paralelo via threads. As respostas chegam em momentos diferentes e precisam ser contabilizadas de forma thread-safe para determinar se a maioria confirmou (e assim avançar o `commit_index`). Na nossa implementação, usamos um `threading.Lock` dedicado para contar as confirmações no `HeartbeatManager`.

- **Garantia de um único voto por termo**: cada nó só pode votar em um candidato por termo. Se dois candidatos solicitam voto ao mesmo nó no mesmo termo, o campo `voted_for` garante que apenas o primeiro pedido é aceito — mas esse campo precisa ser protegido contra acesso concorrente.

## 2. Como é o tipo de consistência no Raft?

O Raft implementa **consistência forte (linearizabilidade)** através das seguintes garantias:

- **Líder único por termo**: em qualquer termo, no máximo um líder pode ser eleito, pois é necessária a maioria dos votos e cada nó vota apenas uma vez por termo. Como só existe uma maioria possível em um cluster, dois candidatos não podem ambos obter maioria no mesmo termo.

- **Log replicado e ordenado**: todas as escritas passam pelo líder, que atribui um índice sequencial a cada entrada. Os followers aceitam as entradas na mesma ordem, garantindo que todos os logs convergem para a mesma sequência.

- **Commit por maioria**: uma entrada só é considerada committed quando a maioria dos nós a confirmou no seu log. Isso garante que a entrada sobrevive a falhas — qualquer maioria futura terá pelo menos um nó que contém a entrada committed.

- **Leitura pelo líder**: como o cliente sempre se comunica com o líder (descoberto via nameserver), as leituras refletem o estado mais recente committed. Isso evita leituras obsoletas que poderiam ocorrer se followers fossem consultados diretamente.

Em termos do teorema CAP, o Raft prioriza **Consistência (C)** e **Tolerância a Partições (P)**, sacrificando **Disponibilidade (A)** — se a maioria dos nós estiver indisponível, o cluster para de aceitar escritas ao invés de arriscar inconsistência.

## 3. Como o algoritmo evita inconsistências nos dados mesmo com falhas?

O Raft possui múltiplos mecanismos para manter a consistência mesmo quando nós falham:

- **Commit apenas com maioria**: o líder só avança o `commit_index` quando a maioria dos followers confirma a replicação. Isso significa que, mesmo que alguns nós falhem, os dados committed estão presentes em pelo menos a maioria do cluster. Na nossa implementação, o líder conta os `success=True` recebidos e só avança o commit se `success_count >= MAJORITY`.

- **Persistência do log no líder**: quando um líder cai e uma nova eleição ocorre, o novo líder terá o log mais atualizado (pois recebeu maioria de votos de nós que já tinham as entradas committed). Os followers que estavam atrasados recebem as entradas corretas via `AppendEntries` do novo líder.

- **Termos monotonicamente crescentes**: cada eleição incrementa o termo. RPCs com termos obsoletos são rejeitados. Se um nó que estava offline volta com um termo antigo, ele automaticamente faz step-down para follower ao receber um heartbeat ou RequestVote com termo maior, adotando o log do líder atual.

- **Heartbeats periódicos**: o líder envia heartbeats a cada 200ms. Isso mantém os followers atualizados e impede eleições desnecessárias. Se o líder falha, a ausência de heartbeats faz com que o election timeout de algum follower expire, disparando uma nova eleição automaticamente.

- **Rejeição de líderes obsoletos**: se um nó recebe um `AppendEntries` de um líder com termo menor que o seu, ele rejeita a mensagem. Isso impede que um líder antigo que volta à rede sobrescreva dados mais recentes.

## 4. Quais problemas podem ocorrer se temporizadores e threads não forem corretamente sincronizados na implementação?

A sincronização incorreta de temporizadores e threads pode causar diversos problemas graves:

- **Eleições desnecessárias (election storms)**: se o election timeout não for corretamente resetado ao receber um heartbeat válido (por exemplo, por uma race condition entre a thread do tick loop e a thread que processa o `AppendEntries`), o nó pode acreditar erroneamente que o líder falhou e iniciar uma eleição, derrubando o líder legítimo. Isso pode levar a um ciclo instável de eleições.

- **Dupla votação (safety violation)**: se o campo `voted_for` não estiver protegido por um lock, dois RPCs de `request_vote` processados simultaneamente podem ambos ler `voted_for = None` antes que qualquer um escreva, resultando no nó votando em dois candidatos diferentes no mesmo termo. Isso viola a regra fundamental de um voto por termo e pode causar **dois líderes simultâneos (split-brain)**.

- **Corrida entre eleição e heartbeat**: um nó pode estar no meio de uma transição para candidato (incrementando termo, votando em si) quando recebe um heartbeat do líder atual. Se essas operações não forem atômicas, o nó pode ficar em um estado inconsistente — por exemplo, com o termo incrementado mas sem ter completado a transição de estado.

- **Heartbeat timeout desincronizado**: se o heartbeat timeout do líder não for corretamente resetado, ele pode enviar heartbeats em rajadas (múltiplos seguidos) ou com atraso, causando sobrecarga na rede ou fazendo followers acreditarem que o líder caiu.

- **Commit index inconsistente**: se o líder atualizar o `commit_index` sem sincronização adequada com a contagem de confirmações dos followers (que chegam em threads paralelas), ele pode avançar o commit prematuramente (antes da maioria confirmar) ou tardiamente, causando inconsistência ou atraso na aplicação dos comandos.

Na nossa implementação, todos esses problemas são mitigados pelo uso de um `threading.Lock` no `RaftNodeProxy` que serializa todo acesso ao estado do nó, garantindo que transições de estado e verificações de timeout sejam atômicas.
