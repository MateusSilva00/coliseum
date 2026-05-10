from src.client.client import RaftClient


def main() -> None:
    RaftClient().start()


if __name__ == "__main__":
    main()
