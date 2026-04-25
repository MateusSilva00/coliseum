import asyncio
import os
from time import monotonic, time

from loguru import logger

from src.core.models import NodeState, RaftNode


async def init():
    node_name = os.getenv("NODE_NAME", "unknown_node")
    node = RaftNode()

    time_until_timeout = (node.election_timeout - (monotonic() * 1000)) / 1000

    logger.info(
        f"[{node_name}]-[{node.node_id}] iniciado como {node.state.upper()} | Timeout: {time_until_timeout:.2f}s"
    )

    try:
        while True:
            now_ms = monotonic() * 1000
            if node.is_election_expired:
                node.state = NodeState.Candidate
                node.term += 1
                time_until_timeout = (node.election_timeout - now_ms) / 1000
                logger.info(f"[{node.node_id}] timeout expirado")
                logger.info(f"[{node.node_id}] mudou para {node.state.upper()}")
                logger.info(
                    f"[{node.node_id}] iniciou eleição para o termo {node.term} |"
                )
                break

            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Erro durante a inicialização: {e}")


if __name__ == "__main__":
    asyncio.run(init())
