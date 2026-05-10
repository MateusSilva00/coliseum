import threading

import Pyro5.api
import Pyro5.errors

from src.core.config import NODE_URIS
from src.core.logging import logger
from src.core.models import NodeState
from src.server.proxy import RaftNodeProxy

_TOTAL_NODES = len(NODE_URIS)
_MAJORITY = (_TOTAL_NODES // 2) + 1


class HeartbeatManager:
    """
    Encapsula o envio periódico de heartbeats (AppendEntries) pelo líder
    para todos os followers, incluindo replicação de log.

    O líder envia seu log completo a cada heartbeat. Se a maioria dos
    followers confirmar, o commit_index avança.
    """

    def __init__(self, proxy: RaftNodeProxy) -> None:
        self._proxy = proxy

    @property
    def _node_name(self) -> str:
        return self._proxy.node.node_name

    def run(self) -> None:
        """
        Envia AppendEntries para todos os peers em paralelo.

        Chamado pelo tick loop quando o heartbeat timeout expira
        e o nó é líder.
        """
        with self._proxy.lock:
            current_term = self._proxy.node.term
            entries = list(self._proxy.node.log)
            commit_index = self._proxy.node.commit_index
            self._proxy.node.reset_heartbeat_timeout()

        # Conta confirmações para calcular commit
        success_count = 1  # o líder conta como 1
        count_lock = threading.Lock()

        def send_and_count(peer_name: str, peer_uri: str) -> None:
            nonlocal success_count
            ok = self._send_to_peer(
                peer_name, peer_uri, current_term, entries, commit_index
            )
            if ok:
                with count_lock:
                    success_count += 1

        threads = []
        for peer_name, peer_uri in NODE_URIS.items():
            if peer_name == self._node_name:
                continue
            t = threading.Thread(
                target=send_and_count,
                args=(peer_name, peer_uri),
                daemon=True,
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=3)

        # Atualiza commit_index se a maioria confirmou
        with self._proxy.lock:
            if (
                self._proxy.node.state == NodeState.Leader
                and self._proxy.node.log
                and success_count >= _MAJORITY
            ):
                last_index = len(self._proxy.node.log)
                if last_index > self._proxy.node.commit_index:
                    old = self._proxy.node.commit_index
                    self._proxy.node.commit_index = last_index
                    logger.success(
                        f"[{self._node_name}] commit_index avançou {old} → {last_index}"
                    )

    def _send_to_peer(
        self,
        peer_name: str,
        peer_uri: str,
        current_term: int,
        entries: list,
        commit_index: int,
    ) -> bool:
        """Envia AppendEntries para um peer. Retorna True se o peer confirmou."""
        try:
            with Pyro5.api.Proxy(peer_uri) as peer:
                peer._pyroTimeout = 2
                response = peer.append_entries(
                    self._node_name,
                    current_term,
                    entries,
                    commit_index,
                )

            peer_term = response["term"]

            if self._detect_higher_term(peer_name, peer_term):
                return False

            return response["success"]

        except Pyro5.errors.CommunicationError:
            logger.warning(
                f"[{self._node_name}] heartbeat falhou — {peer_name} inacessível"
            )
            return False
        except Exception as e:
            logger.error(
                f"[{self._node_name}] erro ao enviar heartbeat para {peer_name}: {e}"
            )
            return False

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
