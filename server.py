import Pyro5.api


@Pyro5.api.expose
class GreetingMaker(object):
    def get_fortune(self, name):
        return (
            f"Hello, {name}. Here is your fortune message:\n"
            "Behold the warranty -- the bold print giveth and the fine print taketh away."
        )

    def somar_numeros(self, x: int, y: int) -> str:
        return f"O resultado da sua soma é {x + y}!"


daemon = Pyro5.api.Daemon()
ns = Pyro5.api.locate_ns()
uri = daemon.register(GreetingMaker)
ns.register("example.greeting", uri)

print(f"Ready")
daemon.requestLoop()
