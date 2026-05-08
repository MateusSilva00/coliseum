import threading

import Pyro5.api
import Pyro5.errors

from src.core.config import NODE_URIS
from src.core.logging import logger
from src.core.models import NodeState
from src.server.proxy import RaftNodeProxy

_TOTAL_NODES = len(NODE_URIS)


class HeartbeatManager:
    """
    Encapsula o envio periódico de heartbeats (AppendEntries vazios)
    pelo líder para todos os followers.

    Responsabilidade única: enviar heartbeats e detectar se algum peer
    possui um termo maior (caso em que o líder faz step-down).
    Os heartbeats são enviados em paralelo via threads para que o
    timeout de um peer offline não atrase os demais.
    """

    def __init__(self, proxy: RaftNodeProxy) -> None:
        self._proxy = proxy

    @property
    def _node_name(self) -> str:
        return self._proxy.node.node_name

    def run(self) -> None:
        """
        Envia AppendEntries (heartbeat) para todos os peers em paralelo.

        Chamado pelo tick loop quando o heartbeat timeout expira
        e o nó é líder.
        """
        with self._proxy.lock:
            current_term = self._proxy.node.term
            self._proxy.node.reset_heartbeat_timeout()

        threads = []
        for peer_name, peer_uri in NODE_URIS.items():
            if peer_name == self._node_name:
                continue

            t = threading.Thread(
                target=self._send_to_peer,
                args=(peer_name, peer_uri, current_term),
                daemon=True,
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=3)

    def _send_to_peer(
        self, peer_name: str, peer_uri: str, current_term: int
    ) -> None:
        """Envia heartbeat para um peer individual."""
        try:
            with Pyro5.api.Proxy(peer_uri) as peer:
                peer._pyroTimeout = 2
                response = peer.append_entries(self._node_name, current_term)

            peer_term = response["term"]

            if self._detect_higher_term(peer_name, peer_term):
                return  # step-down realizado

        except Pyro5.errors.CommunicationError:
            logger.warning(
                f"[{self._node_name}] heartbeat falhou — {peer_name} inacessível"
            )
        except Exception as e:
            logger.error(
                f"[{self._node_name}] erro ao enviar heartbeat para {peer_name}: {e}"
            )

    def _detect_higher_term(self, peer_name: str, peer_term: int) -> bool:
        """
        Verifica se o peer respondeu com um termo maior.
        Se sim, faz step-down imediato para follower.
        """
        with self._proxy.lock:
            if peer_term > self._proxy.node.term:
                self._proxy.node.become_follower(peer_term)
                logger.warning(
                    f"[{self._node_name}] peer {peer_name} tem termo maior "
                    f"({peer_term}), descendo para follower"
                )
                return True
        return False
