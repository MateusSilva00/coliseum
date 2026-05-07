from enum import Enum
from random import uniform
from time import monotonic
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field, computed_field

ELECTION_TIMEOUT_RANGE = (5000, 30000)
HEARTBEAT_INTERVAL = 2000  # ms — intervalo entre heartbeats do líder


class Daemon(BaseModel):
    port: int
    objectId: str


class NodeState(str, Enum):
    Follower = "Follower"
    Leader = "Leader"
    Candidate = "Candidate"


class RaftNode(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    node_name: str = Field(default="unknown")
    state: NodeState = Field(default=NodeState.Follower)
    election_timeout: float = Field(
        default_factory=lambda: (monotonic() * 1000) + uniform(*ELECTION_TIMEOUT_RANGE)
    )
    heartbeat_timeout: float = Field(
        default_factory=lambda: (monotonic() * 1000) + HEARTBEAT_INTERVAL
    )
    term: int = Field(default=0)
    voted_for: Optional[str] = None
    votes_received: int = Field(default=0)
    log: List[Dict[str, Any]] = Field(default_factory=list)
    commit_index: int = Field(default=0)

    # ── Timeouts ────────────────────────────────────────────────────────

    @computed_field
    @property
    def is_election_expired(self) -> bool:
        return (monotonic() * 1000) >= self.election_timeout

    @computed_field
    @property
    def is_heartbeat_due(self) -> bool:
        """Retorna True se está na hora do líder enviar heartbeat."""
        return (monotonic() * 1000) >= self.heartbeat_timeout

    def reset_election_timeout(self) -> float:
        delay = uniform(*ELECTION_TIMEOUT_RANGE)
        self.election_timeout = (monotonic() * 1000) + delay
        return delay / 1000

    def reset_heartbeat_timeout(self) -> None:
        self.heartbeat_timeout = (monotonic() * 1000) + HEARTBEAT_INTERVAL

    # ── Transições de estado ────────────────────────────────────────────

    def become_candidate(self) -> None:
        """Transiciona para Candidate: incrementa termo, vota em si, reseta timeout."""
        self.state = NodeState.Candidate
        self.term += 1
        self.voted_for = self.node_name
        self.votes_received = 1  # auto-voto
        delay = self.reset_election_timeout()
        logger.info(
            f"[{self.node_name}] → CANDIDATE | termo={self.term} | "
            f"votou em si mesmo | novo timeout={delay:.2f}s"
        )

    def become_follower(self, new_term: int) -> None:
        """Step-down para Follower ao receber termo maior."""
        old_state = self.state.value
        self.state = NodeState.Follower
        self.term = new_term
        self.voted_for = None
        self.votes_received = 0
        self.reset_election_timeout()
        logger.info(
            f"[{self.node_name}] {old_state} → FOLLOWER | termo atualizado={new_term}"
        )

    def become_leader(self) -> None:
        """Transiciona para Leader após obter maioria dos votos."""
        self.state = NodeState.Leader
        self.votes_received = 0
        self.reset_heartbeat_timeout()
        logger.success(
            f"[{self.node_name}] → LEADER | termo={self.term} | "
            f"eleito com maioria dos votos"
        )

    # ── Lógica de concessão de voto ─────────────────────────────────────

    def grant_vote(
        self,
        candidate_id: str,
        candidate_term: int,
    ) -> Tuple[int, bool]:
        """
        Decide se concede voto ao candidato.
        Retorna (term_atual, vote_granted).
        """
        # 1. Candidato com termo inferior → rejeita
        if candidate_term < self.term:
            logger.info(
                f"[{self.node_name}] REJEITOU voto para {candidate_id} | "
                f"termo do candidato ({candidate_term}) < meu termo ({self.term})"
            )
            return (self.term, False)

        # 2. Candidato com termo superior → step-down
        if candidate_term > self.term:
            self.become_follower(candidate_term)

        # 3. Já votou neste termo para outro candidato → rejeita
        if self.voted_for is not None and self.voted_for != candidate_id:
            logger.info(
                f"[{self.node_name}] REJEITOU voto para {candidate_id} | "
                f"já votou em {self.voted_for} no termo {self.term}"
            )
            return (self.term, False)

        # 4. Concede voto
        self.voted_for = candidate_id
        self.reset_election_timeout()
        logger.success(
            f"[{self.node_name}] VOTOU em {candidate_id} | termo={self.term}"
        )
        return (self.term, True)

    # ── AppendEntries (heartbeat + replicação futura) ───────────────────

    def handle_append_entries(
        self,
        leader_id: str,
        leader_term: int,
        entries: List[Dict[str, Any]],
    ) -> Tuple[int, bool]:
        """
        Processa um AppendEntries RPC (heartbeat ou replicação).
        Retorna (term_atual, success).
        """
        # 1. Líder com termo inferior → rejeita
        if leader_term < self.term:
            logger.info(
                f"[{self.node_name}] REJEITOU append_entries de {leader_id} | "
                f"termo do líder ({leader_term}) < meu termo ({self.term})"
            )
            return (self.term, False)

        # 2. Reconhece a autoridade do líder → atualiza termo e reseta timeout
        if leader_term > self.term or self.state != NodeState.Follower:
            old_state = self.state.value
            self.state = NodeState.Follower
            self.term = leader_term
            self.voted_for = None
            self.votes_received = 0
            if old_state != NodeState.Follower.value:
                logger.info(
                    f"[{self.node_name}] {old_state} → FOLLOWER | "
                    f"reconheceu líder {leader_id} no termo {leader_term}"
                )

        self.reset_election_timeout()

        # 3. Heartbeat (entries vazio) — apenas confirma
        if not entries:
            logger.debug(
                f"[{self.node_name}] ♥ heartbeat de {leader_id} | termo={leader_term}"
            )
            return (self.term, True)

        # 4. Replicação de log (para implementação futura)
        # TODO: processar entries e atualizar log
        return (self.term, True)

    # ── Representação ───────────────────────────────────────────────────

    def __str__(self) -> str:
        time_until_timeout = (self.election_timeout - (monotonic() * 1000)) / 1000
        return (
            f"Node(\n"
            f"  node_name={self.node_name},\n"
            f"  node_id={self.node_id},\n"
            f"  state={self.state.value},\n"
            f"  term={self.term},\n"
            f"  voted_for={self.voted_for},\n"
            f"  election_timeout={time_until_timeout:.2f}s"
            f")"
        )


if __name__ == "__main__":
    node = RaftNode()
    print(node)
