import os

from src.server.server import RaftServer


def main() -> None:
    node_name = os.getenv("NODE_NAME", "unknown_node")
    RaftServer(node_name).start()


if __name__ == "__main__":
    main()
