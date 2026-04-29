import asyncio
import os
from time import time

from loguru import logger
import Pyro5.api
import Pyro5.errors

import threading

from src.core.models import RaftNode
from src.core.config import (
    NODE_OBJECT_IDS,
    NODE_PORTS,
    NODE_URIS,
)


@Pyro5.api.expose
class RaftNodeProxy:
    def __init__(self, node: RaftNode):
        self.node = node

    def ping(self, from_node: str) -> str:
        logger.info(f"Recebido ping de {from_node}")
        return f"Pong from {self.node.node_id}"


def _schedule_ping(daemon: Pyro5.api.Daemon, node_name: str) -> None:
    def _ping_peers():
        time.sleep(
            5
        )  # Aguarda um pouco para garantir que os outros nós estejam prontos
        for peer_name, peer_uri in NODE_URIS.items():
            if peer_name == node_name:
                continue
            try:
                with Pyro5.api.Proxy(peer_uri) as peer:
                    response = peer.ping(node_name)
                    logger.info(f"Ping para {peer_name} bem-sucedido: {response}")
            except Pyro5.errors.CommunicationError:
                logger.warning(f"Não foi possível pingar {peer_name} em {peer_uri}")

    thread = threading.Thread(target=_ping_peers, daemon=True)
    thread.start()


def main():
    node_name = os.getenv("NODE_NAME", "unknown_node")
    port = NODE_PORTS[node_name]
    object_id = NODE_OBJECT_IDS[node_name]

    logger.info(f"[{node_name}] subindo Daemon na porta {port} | objectId={object_id}")
    daemon = Pyro5.api.Daemon(host="0.0.0.0", port=port)

    node = RaftNodeProxy(node=RaftNode())
    uri = daemon.register(node, objectId=object_id)

    logger.success(f"[{node_name}] registrado com URI: {uri}")
    logger.info(f"[{node_name}] aguardando requisições...")

    _schedule_ping(daemon, node_name)

    daemon.requestLoop()

    # time_until_timeout = (node.election_timeout - (monotonic() * 1000)) / 1000

    # logger.info(
    #     f"[{node_name}]-[{node.node_id}] iniciado como {node.state.upper()} | Timeout: {time_until_timeout:.2f}s"
    # )

    # try:
    #     while True:
    #         now_ms = monotonic() * 1000
    #         if node.is_election_expired:
    #             node.state = NodeState.Candidate
    #             node.term += 1
    #             time_until_timeout = (node.election_timeout - now_ms) / 1000
    #             logger.info(f"[{node.node_id}] timeout expirado")
    #             logger.info(f"[{node.node_id}] mudou para {node.state.upper()}")
    #             logger.info(
    #                 f"[{node.node_id}] iniciou eleição para o termo {node.term} |"
    #             )
    #             break

    #         await asyncio.sleep(0.1)
    # except Exception as e:
    #     logger.error(f"Erro durante a inicialização: {e}")


if __name__ == "__main__":
    asyncio.run(main())
