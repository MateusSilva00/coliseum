import threading

import Pyro5.api

from src.core.logging import logger
from src.core.models import RaftNode


class RaftNodeProxy:
    """
    Expõe via Pyro5 apenas os RPCs do protocolo Raft.

    Cada método público que deve ser acessível remotamente recebe
    @Pyro5.api.expose individualmente, evitando que métodos internos
    fiquem acessíveis pela rede.
    """

    def __init__(self, node: RaftNode) -> None:
        self.node = node
        self.lock = threading.Lock()

    @Pyro5.api.expose
    def request_vote(self, candidate_id: str, candidate_term: int) -> dict:
        """
        RPC RequestVote do protocolo Raft.
        Retorna {"term": int, "vote_granted": bool}.
        """
        with self.lock:
            term, granted = self.node.grant_vote(candidate_id, candidate_term)
            return {"term": term, "vote_granted": granted}

    @Pyro5.api.expose
    def ping(self, from_node: str) -> str:
        """RPC de diagnóstico de conectividade."""
        logger.info(f"[{self.node.node_name}] ping recebido de {from_node}")
        return f"Pong from {self.node.node_name}"
