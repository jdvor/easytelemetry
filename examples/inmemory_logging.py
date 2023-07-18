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


telemetry = build("example")

apples = telemetry.metric_incr("apples")
pears = telemetry.metric_incr("pears", props={"orange": 487.2})
millis = telemetry.metric("millis")
rpm = telemetry.metric("rpm")
sumo = telemetry.metric("sumo")

print(telemetry.describe())

try:
    beta()
except ZeroDivisionError as e:
    telemetry.root.exception(e, orderno=666, god="Quetzalcoatl")

telemetry.root.debug("debugging message %s", 1)
telemetry.root.info("informational message %s", 1)
telemetry.root.info(
    "informational message %s with custom dimensions",
    1,
    orderno=1,
    god="Amon Ra",
)
telemetry.root.warn("warning message %s", 1)
telemetry.root.error("error message %s", 1)
telemetry.root.error(
    "error message %s with custom dimensions",
    1,
    orderno=1,
    god="Quetzalcoatl",
)
telemetry.root.critical("critical message %s", 1)

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

telemetry.print_data()
