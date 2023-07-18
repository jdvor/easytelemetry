from __future__ import annotations

import pytest

from easytelemetry import Level
from easytelemetry.appinsights import (
    AppInsightsTelemetry,
    ConnectionString,
    MockPublisher,
    Options,
    build,
)


def create_options() -> Options:
    cs = ConnectionString(
        instrumentation_key="00000000-0000-0000-0000-000000000000"
    )
    return Options(connection=cs, min_level=Level.DEBUG)


def create_sut() -> (AppInsightsTelemetry, MockPublisher):
    options = create_options()
    pub = MockPublisher()
    ait = build("tests", options=options, publisher=pub)
    return ait, pub


@pytest.fixture
def options() -> Options:
    return create_options()


@pytest.fixture
def sut() -> (AppInsightsTelemetry, MockPublisher):
    return create_sut()
