from shared import wire_up_src_dir

wire_up_src_dir()

from dotenv import load_dotenv

from easytelemetry.appinsights.impl import build
from easytelemetry.interface import Telemetry

load_dotenv(dotenv_path=".env", verbose=True)


def alpha():
    return 1 / 0


def beta():
    return alpha()


with build("exceptional") as telemetry:
    telemetry: Telemetry

    print(telemetry.describe())

    try:
        beta()
    except ZeroDivisionError as e:
        telemetry.root.exception(e, orderno=666, god="Quetzalcoatl")

print("done")
