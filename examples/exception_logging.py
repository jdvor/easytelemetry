#!/usr/bin/env python

from shared import ensure_env

from easytelemetry import Telemetry
from easytelemetry.appinsights import build


ensure_env()


def alpha():
    return 1 / 0


def beta():
    return alpha()


def main():
    with build("example") as t:
        t: Telemetry
        try:
            beta()
        except ZeroDivisionError as e:
            t.root.exception(e, orderno=666, god="Quetzalcoatl")


if __name__ == "__main__":
    main()