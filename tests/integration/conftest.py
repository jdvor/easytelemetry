from __future__ import annotations

import os
import threading

from dotenv import load_dotenv
import pytest

from easytelemetry.appinsights import Options, build


def ensure_env() -> None:
    csname = Options.CONNECTION_STRING_ENV_VAR
    if os.environ.get(csname):
        return
    wd = os.path.dirname(os.path.abspath(__file__))
    loc1 = os.path.join(wd, ".env")
    loc2 = os.path.normpath(os.path.join(wd, "../.env"))
    loc3 = os.path.normpath(os.path.join(wd, "../../.env"))
    for loc in [loc1, loc2, loc3]:
        if os.path.isfile(loc):
            load_dotenv(dotenv_path=loc)
    if not os.environ.get(csname):
        raise EnvironmentError(f"environment variable '{csname}' not set")


@pytest.fixture(scope="session")
def serial():
    yield threading.Lock()


@pytest.fixture(scope="session")
def options():
    ensure_env()
    return Options.from_env("tests")


@pytest.fixture(scope="session")
def ait(options):
    return build("tests", options=options)


@pytest.fixture
def telemetry(serial, ait):
    with serial:
        yield ait
