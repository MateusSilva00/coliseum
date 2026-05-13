import time

import Pyro5.api
import Pyro5.errors

from src.core.config import LEADER_NS_NAME, NAMESERVER_HOST, NAMESERVER_PORT
from src.core.logging import logger


class RaftClient:
    """
    Cliente REPL que se conecta ao líder do cluster Raft via nameserver
    e envia comandos para replicação no log.
    """

    _RETRY_DELAY: float = 2.0

    def __init__(self) -> None:
        self._leader_uri: str | None = None

    def start(self) -> None:
        """Inicia o REPL interativo."""
        logger.info("Cliente Raft iniciado")
        print("\n╔══════════════════════════════════════════╗")
        print("║          RAFT CLIENT — REPL                ║")
        print("╠════════════════════════════════════════════╣")
        print("║  exit    → encerrar                        ║")
        print("║  Qualquer outro texto → comando replicado  ║")
        print("╚════════════════════════════════════════════╝\n")

        while True:
            try:
                cmd = input("raft> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nEncerrando...")
                break

            if not cmd:
                continue

            if cmd.lower() == "exit":
                print("Encerrando...")
                break

            else:
                self._handle_command(cmd)

    # ── Comandos ─────────────────────────────────────────────────────────

    def _handle_command(self, command: str) -> None:
        """Envia um comando ao líder para replicação."""
        leader = self._get_leader_proxy()
        if leader is None:
            return

        try:
            response = leader.submit_command(command)
            if response["success"]:
                print(
                    f"Comando aceito pelo líder | "
                    f"index={response['index']} | termo={response['term']}"
                )
            else:
                error = response.get("error", "unknown")
                if error == "not_leader":
                    print("Nó não é mais líder — tentando reconectar...")
                    self._leader_uri = None
                    # Retry uma vez
                    leader = self._get_leader_proxy()
                    if leader:
                        response = leader.submit_command(command)
                        if response["success"]:
                            print(
                                f"Comando aceito pelo líder | "
                                f"index={response['index']} | termo={response['term']}"
                            )
                        else:
                            print(f"Falha: {response.get('error', 'unknown')}")
                else:
                    print(f"Erro: {error}")
        except Pyro5.errors.CommunicationError:
            print("Líder inacessível — tentando reconectar...")
            self._leader_uri = None

    # ── Conexão com o líder ──────────────────────────────────────────────

    def _get_leader_proxy(self) -> Pyro5.api.Proxy | None:
        """Retorna um proxy para o líder, buscando no nameserver se necessário."""
        if self._leader_uri is None:
            self._leader_uri = self._lookup_leader()
            if self._leader_uri is None:
                return None

        proxy = Pyro5.api.Proxy(self._leader_uri)
        proxy._pyroTimeout = 5
        return proxy

    def _lookup_leader(self) -> str | None:
        """Pesquisa o URI do líder no nameserver Pyro5."""
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                ns = Pyro5.api.locate_ns(host=NAMESERVER_HOST, port=NAMESERVER_PORT)
                uri = ns.lookup(LEADER_NS_NAME)
                leader_uri = str(uri)
                logger.info(f"Líder encontrado: {leader_uri}")
                return leader_uri
            except Pyro5.errors.NamingError:
                print(
                    f"Nenhum líder registrado ainda "
                    f"(tentativa {attempt}/{max_retries})..."
                )
            except Pyro5.errors.CommunicationError:
                print(
                    f"Nameserver inacessível "
                    f"(tentativa {attempt}/{max_retries})..."
                )

            if attempt < max_retries:
                time.sleep(self._RETRY_DELAY)

        print("Não foi possível encontrar o líder")
        return None
