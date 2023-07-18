from shared import ensure_env

from easytelemetry import Telemetry
from easytelemetry.appinsights import build


ensure_env()


def alpha():
    return 1 / 0


def beta():
    return alpha()


with build("example") as telemetry:
    telemetry: Telemetry

    # print(telemetry.describe())
    try:
        beta()
    except ZeroDivisionError as e:
        telemetry.root.exception(e, orderno=666, god="Quetzalcoatl")

print("done")
