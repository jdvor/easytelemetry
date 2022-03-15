from shared import stdout, wire_up_src_dir

wire_up_src_dir()

from time import sleep

from dotenv import load_dotenv

from easytelemetry.appinsights.impl import build
from easytelemetry.interface import Telemetry

load_dotenv(dotenv_path=".env", verbose=True)


def alpha():
    return 1 / 0


def beta():
    return alpha()


with build("activity") as telemetry:
    telemetry: Telemetry

    print(telemetry.describe())

    stdout("actone")
    with telemetry.activity("actone", props={"countdown": 123}):
        sleep(0.4)

    stdout("acttwo")
    try:
        with telemetry.activity("acttwo"):
            sleep(0.2)
            beta()
    except ZeroDivisionError:
        pass

print("done")
