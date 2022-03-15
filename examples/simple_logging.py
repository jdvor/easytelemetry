from shared import stdout, wire_up_src_dir

wire_up_src_dir()

from dotenv import load_dotenv

from easytelemetry.appinsights.impl import build
from easytelemetry.interface import Telemetry

load_dotenv(dotenv_path=".env", verbose=True)

with build("simple") as telemetry:
    telemetry: Telemetry

    print(telemetry.describe())

    i = 0
    loop = True
    while loop:
        i += 1
        stdout(str(i))

        telemetry.root.debug("debugging message %s", i)
        telemetry.root.info("informational message %s", i)
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

        cli_input = input("next? [Y/n]")
        cli_input = cli_input.strip().lower()
        loop = cli_input == "y" or cli_input == "" or cli_input == "yes"
