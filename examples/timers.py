import threading

from shared import ensure_env

from easytelemetry import Telemetry
from easytelemetry.appinsights import build


ensure_env()

with build("example") as t:
    t: Telemetry
    evt = threading.Event()

    timer1 = t.metric_timer("timer1")
    evt.wait(1.2)
    timer1()

    with t.metric_reusable_timer("timer2"):
        evt.wait(0.7)

    timer3 = t.metric_reusable_timer("timer3")
    timer3.start()
    evt.wait(0.4)
    timer3.stop()
