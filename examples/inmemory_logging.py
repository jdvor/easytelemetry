#!/usr/bin/env python

import random
from time import sleep

from shared import ensure_env, stdout

from easytelemetry.inmemory import build


ensure_env()


def alpha():
    return 1 / 0


def beta():
    return alpha()


def rand_float(a: int, b: int) -> float:
    return random.randrange(1000 * a, 1000 * b) / 1000


def main():
    t = build("example")

    apples = t.metric_incr("apples")
    pears = t.metric_incr("pears", props={"orange": 487.2})
    millis = t.metric("millis")
    rpm = t.metric("rpm")
    sumo = t.metric("sumo")

    try:
        beta()
    except ZeroDivisionError as e:
        t.root.exception(e, orderno=666, god="Quetzalcoatl")

    t.root.debug("debugging message %s", 1)
    t.root.info("informational message %s", 1)
    t.root.info(
        "informational message %s with custom dimensions",
        1,
        orderno=1,
        god="Amon Ra",
    )
    t.root.warn("warning message %s", 1)
    t.root.error("error message %s", 1)
    t.root.error(
        "error message %s with custom dimensions",
        1,
        orderno=1,
        god="Quetzalcoatl",
    )
    t.root.critical("critical message %s", 1)

    for i in range(0, 6):
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
        sumo(x)
        stdout(f"sumo {x}")

        if i < 5:
            stdout("sleeping for 10s...")
            sleep(10)

    t.print_data()


if __name__ == "__main__":
    main()
