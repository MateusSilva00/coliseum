import threading
import time

import Pyro5.api
import Pyro5.errors

from src.core.config import (
    LEADER_NS_NAME,
    NAMESERVER_HOST,
    NAMESERVER_PORT,
    NODE_OBJECT_IDS,
    NODE_PORTS,
    NODE_URIS,
)
from src.core.logging import logger
from src.core.models import NodeState, RaftNode
from src.server.election import ElectionManager
from src.server.proxy import RaftNodeProxy


class RaftServer:
    """
    Orquestra o ciclo de vida completo do nó Raft:
      - Registra o proxy Pyro5 no daemon
      - Mantém o tick loop de election timeout
      - Delega o protocolo de eleição ao ElectionManager
      - Registra a liderança no nameserver ao vencer
    """

    _TICK_INTERVAL: float = 0.2  # segundos entre cada verificação
    _STARTUP_DELAY: float = 5.0  # espera inicial antes do tick loop

    def __init__(self, node_name: str) -> None:
        self._node_name = node_name
        node = RaftNode(node_name=node_name)
        self._proxy = RaftNodeProxy(node=node)
        self._election = ElectionManager(self._proxy)

    def start(self) -> None:
        """Inicializa o daemon Pyro5, inicia o tick loop e entra no request loop."""
        daemon = self._create_daemon()

        tick = threading.Thread(target=self._tick_loop, daemon=True)
        tick.start()

        logger.info(f"[{self._node_name}] aguardando requisições...")
        daemon.requestLoop()

    def _create_daemon(self) -> Pyro5.api.Daemon:
        port = NODE_PORTS[self._node_name]
        object_id = NODE_OBJECT_IDS[self._node_name]

        daemon = Pyro5.api.Daemon(host="0.0.0.0", port=port)
        uri = daemon.register(self._proxy, objectId=object_id)

        logger.success(f"[{self._node_name}] registrado com URI: {uri}")
        logger.info(f"[{self._node_name}] estado inicial:\n{self._proxy.node}")
        return daemon

    def _tick_loop(self) -> None:
        """Verifica periodicamente se o election timeout expirou."""
        time.sleep(self._STARTUP_DELAY)
        logger.info(f"[{self._node_name}] tick loop iniciado")

        while True:
            time.sleep(self._TICK_INTERVAL)
            self._check_election_timeout()

    def _check_election_timeout(self) -> None:
        """Dispara eleição se o timeout tiver expirado num estado elegível."""
        with self._proxy.lock:
            state = self._proxy.node.state
            is_expired = self._proxy.node.is_election_expired

        if state in (NodeState.Follower, NodeState.Candidate) and is_expired:
            won = self._election.run()
            if won:
                self._register_as_leader()

    def _register_as_leader(self) -> None:
        """Registra este nó como líder ativo no nameserver Pyro5."""
        try:
            ns = Pyro5.api.locate_ns(host=NAMESERVER_HOST, port=NAMESERVER_PORT)
            leader_uri = NODE_URIS[self._node_name]
            ns.register(LEADER_NS_NAME, leader_uri)
            logger.success(
                f"[{self._node_name}] registrado como líder no nameserver: "
                f"{LEADER_NS_NAME} → {leader_uri}"
            )
        except Exception as e:
            logger.error(
                f"[{self._node_name}] falha ao registrar líder no nameserver: {e}"
            )
