import os
import threading
import time

from loguru import logger
import Pyro5.api
import Pyro5.errors

from src.core.models import RaftNode, NodeState
from src.core.config import (
    LEADER_NS_NAME,
    NAMESERVER_HOST,
    NAMESERVER_PORT,
    NODE_OBJECT_IDS,
    NODE_PORTS,
    NODE_URIS,
)

TOTAL_NODES = len(NODE_URIS)
MAJORITY = (TOTAL_NODES // 2) + 1  # 3 de 4


@Pyro5.api.expose
class RaftNodeProxy:
    """Proxy Pyro5 que envolve o RaftNode e expõe os RPCs do Raft."""

    def __init__(self, node: RaftNode):
        self.node = node
        self.lock = threading.Lock()

    # ── RPCs expostos ───────────────────────────────────────────────────

    def request_vote(
        self,
        candidate_id: str,
        candidate_term: int,
    ) -> dict:
        """
        RPC RequestVote do Raft.
        Retorna {"term": int, "vote_granted": bool}.
        """
        with self.lock:
            term, granted = self.node.grant_vote(candidate_id, candidate_term)
            return {"term": term, "vote_granted": granted}

    def append_entries(
        self,
        leader_id: str,
        leader_term: int,
        entries: list,
    ) -> dict:
        """
        RPC AppendEntries do Raft (heartbeat quando entries=[]).
        Retorna {"term": int, "success": bool}.
        """
        with self.lock:
            term, success = self.node.handle_append_entries(
                leader_id, leader_term, entries
            )
            return {"term": term, "success": success}

    def ping(self, from_node: str) -> str:
        logger.info(f"Recebido ping de {from_node}")
        return f"Pong from {self.node.node_name}"


# ── Lógica de eleição ──────────────────────────────────────────────────


def _start_election(proxy: RaftNodeProxy, node_name: str) -> None:
    """Inicia uma eleição: torna-se Candidate e solicita votos dos peers."""

    with proxy.lock:
        proxy.node.become_candidate()
        current_term = proxy.node.term

    logger.info(
        f"[{node_name}] solicitando votos dos peers para o termo {current_term}..."
    )

    votes_granted = 1  # auto-voto
    for peer_name, peer_uri in NODE_URIS.items():
        if peer_name == node_name:
            continue

        try:
            with Pyro5.api.Proxy(peer_uri) as peer:
                peer._pyroTimeout = 3
                response = peer.request_vote(node_name, current_term)
                peer_term = response["term"]
                vote_granted = response["vote_granted"]

                with proxy.lock:
                    if peer_term > proxy.node.term:
                        proxy.node.become_follower(peer_term)
                        logger.warning(
                            f"[{node_name}] peer {peer_name} tem termo maior "
                            f"({peer_term}), abortando eleição"
                        )
                        return

                if vote_granted:
                    votes_granted += 1
                    logger.info(
                        f"[{node_name}] recebeu voto de {peer_name} | "
                        f"total={votes_granted}/{TOTAL_NODES}"
                    )

        except Pyro5.errors.CommunicationError:
            logger.warning(
                f"[{node_name}] não conseguiu contatar {peer_name} para votação"
            )
        except Exception as e:
            logger.error(f"[{node_name}] erro ao solicitar voto de {peer_name}: {e}")

    with proxy.lock:
        if proxy.node.state != NodeState.Candidate or proxy.node.term != current_term:
            logger.info(
                f"[{node_name}] eleição cancelada — estado mudou durante a votação"
            )
            return

        proxy.node.votes_received = votes_granted

        if votes_granted >= MAJORITY:
            proxy.node.become_leader()
            _register_leader(node_name)
        else:
            logger.warning(
                f"[{node_name}] eleição falhou | votos={votes_granted}/{TOTAL_NODES} "
                f"(necessário {MAJORITY}) | aguardando próximo timeout"
            )


def _register_leader(node_name: str) -> None:
    """Registra o líder no nameserver Pyro5 para o cliente poder localizá-lo."""
    try:
        ns = Pyro5.api.locate_ns(host=NAMESERVER_HOST, port=NAMESERVER_PORT)
        leader_uri = NODE_URIS[node_name]
        ns.register(LEADER_NS_NAME, leader_uri)
        logger.success(
            f"[{node_name}] registrado como líder no nameserver: "
            f"{LEADER_NS_NAME} → {leader_uri}"
        )
    except Exception as e:
        logger.error(f"[{node_name}] falha ao registrar líder no nameserver: {e}")


# ── Heartbeat do líder ─────────────────────────────────────────────────


def _send_heartbeats(proxy: RaftNodeProxy, node_name: str) -> None:
    """Envia AppendEntries vazio (heartbeat) para todos os followers."""

    with proxy.lock:
        current_term = proxy.node.term
        proxy.node.reset_heartbeat_timeout()

    for peer_name, peer_uri in NODE_URIS.items():
        if peer_name == node_name:
            continue

        try:
            with Pyro5.api.Proxy(peer_uri) as peer:
                peer._pyroTimeout = 2
                response = peer.append_entries(node_name, current_term, [])
                peer_term = response["term"]

                # Se algum follower tem termo maior → step-down
                with proxy.lock:
                    if peer_term > proxy.node.term:
                        proxy.node.become_follower(peer_term)
                        logger.warning(
                            f"[{node_name}] follower {peer_name} tem termo maior "
                            f"({peer_term}), fazendo step-down"
                        )
                        return

        except Pyro5.errors.CommunicationError:
            logger.warning(
                f"[{node_name}] heartbeat falhou para {peer_name} (sem conexão)"
            )
        except Exception as e:
            logger.error(f"[{node_name}] erro no heartbeat para {peer_name}: {e}")

    logger.debug(f"[{node_name}] ♥ heartbeats enviados | termo={current_term}")


# ── Tick loop ──────────────────────────────────────────────────────────


def _tick_loop(proxy: RaftNodeProxy, node_name: str) -> None:
    """
    Loop principal do Raft (roda em thread separada).
    - Follower/Candidate: verifica election timeout
    - Leader: envia heartbeats periodicamente
    """
    time.sleep(5)
    logger.info(f"[{node_name}] tick loop iniciado")

    while True:
        time.sleep(0.1)

        with proxy.lock:
            state = proxy.node.state
            election_expired = proxy.node.is_election_expired
            heartbeat_due = proxy.node.is_heartbeat_due

        # Follower/Candidate → eleição se timeout expirou
        if state in (NodeState.Follower, NodeState.Candidate) and election_expired:
            _start_election(proxy, node_name)

        # Leader → heartbeat se intervalo expirou
        elif state == NodeState.Leader and heartbeat_due:
            _send_heartbeats(proxy, node_name)


# ── Entrypoint ─────────────────────────────────────────────────────────


def main():
    node_name = os.getenv("NODE_NAME", "unknown_node")
    port = NODE_PORTS[node_name]
    object_id = NODE_OBJECT_IDS[node_name]

    logger.info(f"[{node_name}] subindo Daemon na porta {port} | objectId={object_id}")
    daemon = Pyro5.api.Daemon(host="0.0.0.0", port=port)

    node = RaftNode(node_name=node_name)
    proxy = RaftNodeProxy(node=node)
    uri = daemon.register(proxy, objectId=object_id)

    logger.success(f"[{node_name}] registrado com URI: {uri}")
    logger.info(f"[{node_name}] estado inicial:\n{node}")

    tick_thread = threading.Thread(
        target=_tick_loop, args=(proxy, node_name), daemon=True
    )
    tick_thread.start()

    logger.info(f"[{node_name}] aguardando requisições...")
    daemon.requestLoop()


if __name__ == "__main__":
    main()
