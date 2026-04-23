from enum import Enum
from random import uniform
from time import time
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

ELECTION_TIMEOUT = (150, 300)
HEARTBEAT_INTERVAL = 50


class Daemon(BaseModel):
    port: int
    objectId: str


class AllowedStates(str, Enum):
    Follower = "Follower"
    Leader = "Leader"
    Candidate = "Candidate"


class Node(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    state: AllowedStates = Field(default=AllowedStates.Follower)
    election_timeout: float = Field(
        default_factory=lambda: (time() * 1000) + uniform(*ELECTION_TIMEOUT)
    )
    hearbeat_timeout: float = Field(
        default_factory=lambda: (time() * 1000) + HEARTBEAT_INTERVAL
    )
    term: int
    daemon: Daemon
    voted_for: Optional[str]
    log: List[Dict[str, Any]]
    commit_index: int
    # lastApplied: int
    # nextIndex: Dict[str, int]
    # matchIndex: Dict[str, int]

    def __str__(self) -> str:
        return (
            f"Node(\n"
            f"  node_id={self.node_id},\n"
            f"  state={self.state.value},\n"
            f"  election_timeout={self.election_timeout:.2f}ms\n"
            f")"
        )


if __name__ == "__main__":
    node = Node()
    print(node)
