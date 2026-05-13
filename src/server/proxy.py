import threading
from typing import Any, Dict, List, Optional

import Pyro5.api
import Pyro5.errors

from src.core.config import NODE_URIS
from src.core.logging import logger
from src.core.models import NodeState, RaftNode


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
    def request_vote(self, candidate_id: str, candidate_term: int) -> Dict:
        """
        RPC RequestVote do protocolo Raft.
        Retorna {"term": int, "vote_granted": bool}.
        """
        with self.lock:
            term, granted = self.node.grant_vote(candidate_id, candidate_term)
            return {"term": term, "vote_granted": granted}

    @Pyro5.api.expose
    def append_entries(
        self,
        leader_id: str,
        leader_term: int,
        entries: Optional[List[Dict[str, Any]]] = None,
        leader_commit: int = 0,
    ) -> dict:
        """
        RPC AppendEntries do protocolo Raft (heartbeat + replicação de log).
        Retorna {"term": int, "success": bool}.
        """
        with self.lock:
            term, success = self.node.handle_append_entries(
                leader_id,
                leader_term,
                entries,
                leader_commit,
            )
            return {"term": term, "success": success}

    @Pyro5.api.expose
    def submit_command(self, command: str) -> dict:
        """
        RPC para o cliente enviar comandos ao líder.
        Retorna {"success": bool, "index": int, "term": int, "error": str}.
        """
        with self.lock:
            if self.node.state != NodeState.Leader:
                logger.warning(
                    f"[{self.node.node_name}] rejeitou comando — não sou líder"
                )
                return {
                    "success": False,
                    "index": -1,
                    "term": self.node.term,
                    "error": "not_leader",
                }

            entry = self.node.append_log_entry(command)
            return {
                "success": True,
                "index": entry["index"],
                "term": entry["term"],
                "error": "",
            }