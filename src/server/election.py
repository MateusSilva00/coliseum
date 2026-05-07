import Pyro5.api
import Pyro5.errors

from src.core.config import NODE_URIS
from src.core.logging import logger
from src.core.models import NodeState
from src.server.proxy import RaftNodeProxy

_TOTAL_NODES = len(NODE_URIS)
_MAJORITY = (_TOTAL_NODES // 2) + 1


class ElectionManager:
    """
    Encapsula o protocolo de eleição Raft.

    Responsabilidade única: conduzir uma rodada de eleição completa,
    desde tornar-se candidato até contabilizar os votos.
    A decisão do que fazer após a vitória (ex.: registro no nameserver)
    fica a cargo do chamador.
    """

    def __init__(self, proxy: RaftNodeProxy) -> None:
        self._proxy = proxy

    @property
    def _node_name(self) -> str:
        return self._proxy.node.node_name

    def run(self) -> bool:
        """
        Conduz uma eleição completa.

        Retorna True se o nó ganhou (tornou-se líder), False caso contrário.
        """
        with self._proxy.lock:
            self._proxy.node.become_candidate()
            current_term = self._proxy.node.term

        logger.info(
            f"[{self._node_name}] solicitando votos dos peers para o termo {current_term}..."
        )

        votes = self._collect_votes(current_term)
        return self._conclude(votes, current_term)

    def _collect_votes(self, current_term: int) -> int:
        """Solicita votos de todos os peers e devolve a contagem total."""
        votes = 1

        for peer_name, peer_uri in NODE_URIS.items():
            if peer_name == self._node_name:
                continue

            try:
                with Pyro5.api.Proxy(peer_uri) as peer:
                    peer._pyroTimeout = 3
                    response = peer.request_vote(self._node_name, current_term)

                peer_term = response["term"]
                vote_granted = response["vote_granted"]

                if self._detect_higher_term(peer_name, peer_term):
                    return votes  # eleição abortada, step-down já realizado

                if vote_granted:
                    votes += 1
                    logger.info(
                        f"[{self._node_name}] recebeu voto de {peer_name} | "
                        f"total={votes}/{_TOTAL_NODES}"
                    )

            except Pyro5.errors.CommunicationError:
                logger.warning(
                    f"[{self._node_name}] não conseguiu contatar {peer_name} para votação"
                )
            except Exception as e:
                logger.error(
                    f"[{self._node_name}] erro ao solicitar voto de {peer_name}: {e}"
                )

        return votes

    def _detect_higher_term(self, peer_name: str, peer_term: int) -> bool:
        """
        Verifica se o peer respondeu com um termo maior.
        Se sim, faz step-down imediato e retorna True.
        """
        with self._proxy.lock:
            if peer_term > self._proxy.node.term:
                self._proxy.node.become_follower(peer_term)
                logger.warning(
                    f"[{self._node_name}] peer {peer_name} tem termo maior "
                    f"({peer_term}), abortando eleição"
                )
                return True
        return False

    def _conclude(self, votes: int, current_term: int) -> bool:
        """Avalia o resultado e transiciona para líder ou permanece seguidor."""
        with self._proxy.lock:
            state_changed = (
                self._proxy.node.state != NodeState.Candidate
                or self._proxy.node.term != current_term
            )
            if state_changed:
                logger.info(
                    f"[{self._node_name}] eleição cancelada — estado mudou durante a votação"
                )
                return False

            self._proxy.node.votes_received = votes

            if votes >= _MAJORITY:
                self._proxy.node.become_leader()
                return True

            logger.warning(
                f"[{self._node_name}] eleição falhou | votos={votes}/{_TOTAL_NODES} "
                f"(necessário {_MAJORITY}) | aguardando próximo timeout"
            )
            return False
