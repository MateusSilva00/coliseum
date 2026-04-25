from enum import Enum
from random import uniform
from time import monotonic
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field

ELECTION_TIMEOUT_RANGE = (5000, 30000)
HEARTBEAT_INTERVAL = 200


class Daemon(BaseModel):
    port: int
    objectId: str


class NodeState(str, Enum):
    Follower = "Follower"
    Leader = "Leader"
    Candidate = "Candidate"


class RaftNode(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    state: NodeState = Field(default=NodeState.Follower)
    election_timeout: float = Field(
        default_factory=lambda: (monotonic() * 1000) + uniform(*ELECTION_TIMEOUT_RANGE)
    )
    hearbeat_timeout: float = Field(
        default_factory=lambda: (monotonic() * 1000) + HEARTBEAT_INTERVAL
    )
    term: int = Field(default=0)
    # daemon: Daemon
    voted_for: Optional[str] = None
    log: List[Dict[str, Any]] = Field(default_factory=list)
    commit_index: int = Field(default=0)
    # lastApplied: int
    # nextIndex: Dict[str, int]
    # matchIndex: Dict[str, int]

    def __str__(self) -> str:
        time_until_timeout = (self.election_timeout - (monotonic() * 1000)) / 1000
        return (
            f"Node(\n"
            f"  node_id={self.node_id},\n"
            f"  state={self.state.value}\n"
            f"  election_timeout={time_until_timeout:.2f}s"
            f")"
        )

    @computed_field
    def is_election_expired(self) -> bool:
        return (monotonic() * 1000) >= self.election_timeout

    def reset_election_timeout(self) -> float:
        delay = uniform(*ELECTION_TIMEOUT_RANGE)
        self.election_timeout = (monotonic() * 1000) + delay
        return delay / 1000


if __name__ == "__main__":
    node = RaftNode()
    print(node)
