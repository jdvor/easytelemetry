from time import sleep

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
    with telemetry.activity("actone"):
        sleep(0.4)
        try:
            with telemetry.activity("acttwo"):
                sleep(0.2)
                beta()
        except ZeroDivisionError:
            pass

print("done")
