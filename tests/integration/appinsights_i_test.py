"""Filename is little odd, but that's because pytest requires
all test filenames to be unique."""

import time

import pytest

from easytelemetry.appinsights import AppInsightsTelemetry, FlushT


def _assert(result: FlushT) -> None:
    def to_str(errs):
        m1 = "failed to publish data to ingestion endpoint"
        if errs is None:
            return m1
        m2 = (
            str(errs[0])
            if len(errs) == 1
            else "\n".join([str(e) for e in errs])
        )
        return f"{m1}\n\n{m2}"

    success, errors = result
    errmsg = None if success else to_str(errors)
    assert success, errmsg


def func_raise_error() -> None:
    """Raise ZeroDivisionError"""
    _ = 1 / 0


@pytest.mark.integration
def test_simple_logging(telemetry: AppInsightsTelemetry):
    tag = "a1"
    lgr = telemetry.root
    lgr.debug(f"debug in {tag}")
    lgr.info(f"info in {tag}")
    lgr.warn(f"warn in {tag}")
    lgr.error(f"error in {tag}")
    lgr.critical(f"critical in {tag}", god="Quetzalcoatl")

    result = telemetry.flush()
    _assert(result)


@pytest.mark.integration
def test_exception(telemetry: AppInsightsTelemetry):
    try:
        func_raise_error()
    except ZeroDivisionError as e:
        telemetry.root.exception(e)

    result = telemetry.flush()
    _assert(result)


@pytest.mark.integration
def test_metrics(telemetry: AppInsightsTelemetry):
    m1 = telemetry.metric_incr("m1")
    m2 = telemetry.metric_extra("m2", {"group": "Alpha"})
    m1()
    m1()
    m2(42, {"devil": 666})

    result = telemetry.flush()
    _assert(result)


@pytest.mark.integration
def test_activity_on_success(telemetry: AppInsightsTelemetry):
    with telemetry.activity("act1"):
        time.sleep(0.6)

    result = telemetry.flush()
    _assert(result)


@pytest.mark.integration
def test_activity_on_error(telemetry: AppInsightsTelemetry):
    with pytest.raises(ZeroDivisionError):
        with telemetry.activity("act2"):
            time.sleep(0.3)
            func_raise_error()

    result = telemetry.flush()
    _assert(result)
