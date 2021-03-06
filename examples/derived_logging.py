from shared import stdout, wire_up_src_dir

wire_up_src_dir()

from dotenv import load_dotenv

from easytelemetry.appinsights.impl import build
from easytelemetry.interface import Level, Telemetry

load_dotenv(dotenv_path=".env", verbose=True)

with build("derived") as telemetry:
    telemetry: Telemetry

    lgr = telemetry.logger("inderived", Level.WARN, {"aspect": "16:9"})
    print(telemetry.describe())
    i = 0
    loop = True
    while loop:
        i += 1
        stdout(str(i))

        lgr.debug("debugging message %s", i)
        lgr.info("informational message %s", i)
        lgr.warn("warning message %s", i)
        lgr.error("error message %s", i)
        lgr.error(
            "error message %s with custom dimensions",
            i,
            orderno=i,
            god="Quetzalcoatl",
        )

        cli_input = input("next? [Y/n]")
        cli_input = cli_input.strip().lower()
        loop = cli_input == "y" or cli_input == "" or cli_input == "yes"
