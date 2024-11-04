#!/usr/bin/env python

import random
from time import sleep

from shared import ensure_env, stdout

from easytelemetry import Telemetry
from easytelemetry.appinsights import build


ensure_env()


def rand_float(a: int, b: int) -> float:
    return random.randrange(1000 * a, 1000 * b) / 1000


def main():
    with build("example") as t:
        t: Telemetry

        apples = t.metric_incr("apples")
        pears = t.metric_incr("pears", props={"orange": 487.2})
        millis = t.metric("millis")
        rpm = t.metric("rpm")
        sumo = t.metric_extra("sumo")

        print(t.describe())

        for i in range(0, 13):
            apples()
            apples()
            apples()
            stdout("apples +3")

            pears()
            stdout("pears +1")

            x = random.randrange(20, 101)
            millis(x)
            stdout(f"millis {x}")

            x = rand_float(5, 51)
            rpm(x)
            stdout(f"rpm {x}")

            x = rand_float(1, 11)
            sumo(x, {"loc": i})
            stdout(f"sumo {x}")

            if i < 12:
                stdout("sleeping for 10s...")
                sleep(10)

    stdout("done")


if __name__ == "__main__":
    main()