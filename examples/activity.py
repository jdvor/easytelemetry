import threading

from shared import ensure_env

from easytelemetry import Telemetry
from easytelemetry.appinsights import build


ensure_env()


def alpha():
    return 1 / 0


def beta():
    return alpha()


try:
    with build("example") as telemetry:
        telemetry: Telemetry
        evt = threading.Event()

        with telemetry.activity("purchase") as act:
            act.logger.info(f"{act.name} created", order_id="NY9584")
            evt.wait(0.7)
            act.logger.warn("product out of stock", sku="ACM7")
            beta()
except ZeroDivisionError:
    # expected
    pass
