from shared import stdout, wire_up_src_dir

wire_up_src_dir()

import random
from time import sleep

from dotenv import load_dotenv

from easytelemetry.appinsights.impl import build
from easytelemetry.interface import Telemetry

load_dotenv(dotenv_path=".env", verbose=True)


def rand_float(a: int, b: int) -> float:
    return random.randrange(1000 * a, 1000 * b) / 1000


with build("metrics") as telemetry:
    telemetry: Telemetry

    apples = telemetry.metric_incr("apples")
    pears = telemetry.metric_incr("pears", props={"orange": 487.2})
    millis = telemetry.metric("millis")
    rpm = telemetry.metric("rpm")
    sumo = telemetry.metric("sumo")

    print(telemetry.describe())

    for i in range(0, 13):

        # apples()
        # apples()
        # apples()
        # stdout('apples +3')

        pears()
        stdout("pears +1")

        # x = random.randrange(20, 101)
        # millis(x)
        # stdout(f'millis {x}')
        #
        # x = rand_float(5, 51)
        # rpm(x)
        # stdout(f'rpm {x}')
        #
        # x = rand_float(1, 11)
        # sumo(x)
        # stdout(f'sumo {x}')

        if i < 12:
            stdout("sleeping for 10s...")
            sleep(10)

print("done")
