import random
from uuid import uuid4

import Pyro5.api
from loguru import logger

from src.core.models import Daemon


def init_server(daemon: Daemon) -> Pyro5.api.Proxy:
    object_id = daemon.objectId
    port = daemon.port
    uri = f"PYRO:{object_id}@localhost:{port}"
    client = Pyro5.api.Proxy(uri)
    logger.info(f"Client initialized with URI: {uri}")

    daemon = Pyro5.api.Daemon(port=port)
    ns = Pyro5.api.locate_ns()
    ns.register(object_id, uri)
    logger.info(f"Daemon registered with object ID: {object_id} on port: {port}")

    daemon.requestLoop()
    return client


def generate_server() -> Daemon:
    server = Daemon(port=random.randint(5000, 6000), objectId=str(uuid4())[:6])
    return server


if __name__ == "__main__":
    server = generate_server()
    logger.info(f"Generated client: {server}")
    init_server(server)
