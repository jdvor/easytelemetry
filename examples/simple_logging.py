from shared import ensure_env, stdout

from easytelemetry import Telemetry
from easytelemetry.appinsights import Options, build


ensure_env()


def myfunc1(tlm: Telemetry, n: int) -> None:
    tlm.root.info("informational message %s", n)


def configure(opts: Options) -> None:
    opts.debug = True


with build("example", configure) as t:
    t: Telemetry

    i = 0
    loop = True
    while loop:
        i += 1
        stdout(f"i: {i}")

        t.root.debug("debugging message %s", i)
        myfunc1(t, i)
        t.root.info(
            "informational message %s with custom dimensions",
            i,
            orderno=i,
            god="Amon Ra",
        )
        t.root.warn("warning message %s", i)
        t.root.error("error message %s", i)
        t.root.error(
            "error message %s with custom dimensions",
            i,
            orderno=i,
            god="Quetzalcoatl",
        )
        t.root.critical("critical message %s", i)

        print()
        cli_input = input("next? [Y/n]")
        cli_input = cli_input.strip().lower()
        loop = cli_input == "y" or cli_input == "" or cli_input == "yes"
