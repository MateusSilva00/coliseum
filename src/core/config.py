NAMESERVER_HOST = "nameserver"
NAMESERVER_PORT = 9090

LEADER_NS_NAME = "raft.leader"


# Formato: "PYRO:<objectId>@<hostname>:<porta>"
# - objectId  → identificador do objeto registrado no Daemon local do nó
# - hostname  → nome do serviço no docker-compose (resolve via DNS interno)
# - porta     → porta exposta pelo Daemon Pyro5 do nó

NODE_URIS: dict[str, str] = {
    "node_1": "PYRO:raft.node1@node_1:9001",
    "node_2": "PYRO:raft.node2@node_2:9002",
    "node_3": "PYRO:raft.node3@node_3:9003",
    "node_4": "PYRO:raft.node4@node_4:9004",
}

NODE_PORTS: dict[str, int] = {
    "node_1": 9001,
    "node_2": 9002,
    "node_3": 9003,
    "node_4": 9004,
}

NODE_OBJECT_IDS: dict[str, str] = {
    "node_1": "raft.node1",
    "node_2": "raft.node2",
    "node_3": "raft.node3",
    "node_4": "raft.node4",
}
