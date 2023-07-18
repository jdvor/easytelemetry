from time import sleep

from shared import ensure_env

from easytelemetry import Telemetry
from easytelemetry.appinsights import build


ensure_env()

with build("example") as telemetry:
    telemetry: Telemetry

    # print(telemetry.describe())
    timer1 = telemetry.metric_timer("timer1")
    sleep(1.2)
    timer1()

    with telemetry.metric_reusable_timer("timer2"):
        sleep(0.7)

    timer3 = telemetry.metric_reusable_timer("timer3")
    timer3.start()
    sleep(0.4)
    timer3.stop()

print("done")
