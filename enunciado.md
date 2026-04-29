Implementar o algoritmo de consenso Raft para replicação de log entre 4 processos que vão se comunicar através do PyRO.

Inicialização dos processos:
• Inicializem o servidor de nomes do PyRO;
• Inicializem os 4 processos que implementam o Raft como seguidores;
• Informem uma porta ao criar o Daemon e um objectId no registro do objeto com o Daemon. Com essas duas informações, teremos o URI "PYRO:objectId@localhost:porta" de cada objeto PyRO e poderemos deixá-los hard coded;
• Inicializem 1 processo cliente responsável por encaminhar comandos ao líder;

Eleição (valor 10):

• Um dos processos será eleito líder;
• Ao ser eleito como líder, este processo deverá se registrar no serviço de nomes com o nome Líder (sobrescrever a entrada a partir da segunda eleição) e enviar mensagens de heartbeat de tempos em tempos;
• Utilizem temporizadores de eleição aleatórios para evitar que os nós se tornem candidatos ao mesmo tempo;
• Quando um líder falhar, um outro processo será eleito como líder.

Replicação (valor 15):

• O cliente pesquisará o URI do líder no servidor de nomes;
• O cliente enviará comandos ao líder;
• O líder será responsável por receber comandos dos clientes, anexá-los ao seu log e replicá-los aos seguidores;
• Uma entrada no log apenas será efetivada (committed) se a maioria dos seguidores confirmarem ela no seu log;
• O líder transmitirá mensagens periódicas para todos os seguidores para manter sua autoridade e prevenir novas eleições.
