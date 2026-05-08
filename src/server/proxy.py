import threading

import Pyro5.api
import Pyro5.errors

from src.core.config import NODE_URIS
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

    @Pyro5.api.expose
    def append_entries(self, leader_id: str, leader_term: int) -> dict:
        """
        RPC AppendEntries do protocolo Raft (heartbeat).
        Retorna {"term": int, "success": bool}.
        """
        with self.lock:
            term, success = self.node.handle_append_entries(leader_id, leader_term)
            return {"term": term, "success": success}

    @Pyro5.api.expose
    def get_cluster_status(self) -> dict:
        """
        Verifica quais nós do cluster estão online via ping.
        Retorna {"online": [...], "offline": [...], "total": int}.
        """
        online = []
        offline = []

        for peer_name, peer_uri in NODE_URIS.items():
            if peer_name == self.node.node_name:
                online.append(peer_name)  # eu mesmo estou online
                continue
            try:
                with Pyro5.api.Proxy(peer_uri) as peer:
                    peer._pyroTimeout = 2
                    peer.ping(self.node.node_name)
                online.append(peer_name)
            except Pyro5.errors.CommunicationError:
                offline.append(peer_name)

        return {
            "online": online,
            "offline": offline,
            "total": len(NODE_URIS),
        }
