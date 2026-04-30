# ⚔️ Coliseum — Consenso Raft com Pyro5

Implementação do algoritmo de consenso **Raft** para replicação de log entre **4 nós distribuídos**, utilizando **Pyro5** (Python Remote Objects) como mecanismo de comunicação remota. Projeto desenvolvido para a disciplina de Sistemas Distribuídos — UTFPR.

## 📐 Arquitetura

- **Nameserver Pyro5** — Serviço de nomes centralizado para descoberta de objetos remotos.
- **4 Nós Raft** — Cada nó inicia como **Follower** e participa do protocolo de eleição de líder e replicação de log.
- **Cliente** — Processo que consulta o líder via nameserver e envia comandos para replicação.

## 🛠️ Tecnologias

- **Python 3.12**
- **[Pyro5](https://pyro5.readthedocs.io/)** — Comunicação remota entre objetos Python
- **[Pydantic](https://docs.pydantic.dev/)** — Modelagem e validação de dados
- **[Loguru](https://loguru.readthedocs.io/)** — Logging estruturado
- **[uv](https://docs.astral.sh/uv/)** — Gerenciador de pacotes e ambientes Python
- **Docker / Docker Compose** — Orquestração dos containers

## 🚀 Como Executar

### Pré-requisitos

- [Docker](https://www.docker.com/) e [Docker Compose](https://docs.docker.com/compose/) instalados
- Ou, para execução local: **Python 3.12+** e **[uv](https://docs.astral.sh/uv/)**

---

### Opção 1 — Docker Compose (recomendado)

**Linux / macOS:**

```bash
# Build + execução em um comando
./run.sh
```

**Windows / Manual:**

```bash
# Limpar ambiente anterior
docker compose down --volumes --remove-orphans

# Build e execução dos containers
docker compose up --build -d

# Acompanhar logs em tempo real
docker compose logs -f
```

Isso sobe automaticamente:
1. O **nameserver** Pyro5 na porta `9090`
2. Os **4 nós Raft** nas portas `9001`–`9004`

Para parar o cluster:

```bash
docker compose down
```
