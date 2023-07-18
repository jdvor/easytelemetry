from shared import ensure_env, stdout

from easytelemetry import Telemetry
from easytelemetry.appinsights import Options, build


ensure_env()


def myfunc1(n: int) -> None:
    telemetry.root.info("informational message %s", n)


def configure(opts: Options) -> None:
    opts.debug = True


with build("example", configure) as telemetry:
    telemetry: Telemetry

    print(telemetry.describe())
    print("---")

    i = 0
    loop = True
    while loop:
        i += 1
        stdout(f"i: {i}")

        telemetry.root.debug("debugging message %s", i)
        myfunc1(i)
        telemetry.root.info(
            "informational message %s with custom dimensions",
            i,
            orderno=i,
            god="Amon Ra",
        )
        telemetry.root.warn("warning message %s", i)
        telemetry.root.error("error message %s", i)
        telemetry.root.error(
            "error message %s with custom dimensions",
            i,
            orderno=i,
            god="Quetzalcoatl",
        )
        telemetry.root.critical("critical message %s", i)

        print()
        cli_input = input("next? [Y/n]")
        cli_input = cli_input.strip().lower()
        loop = cli_input == "y" or cli_input == "" or cli_input == "yes"

print("done")
