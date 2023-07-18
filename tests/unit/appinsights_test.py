import time
from typing import Tuple

import pytest
from utils import (
    contains_datapoint,
    contains_ikey,
    contains_prop,
    contains_prop_keys,
    func_raise_error,
    is_exception,
    is_metric,
    is_trace,
)

from easytelemetry.appinsights import AppInsightsTelemetry, MockPublisher


def _assert(pub: MockPublisher) -> None:
    """Common (shared) asserts"""
    assert pub.all(lambda x: contains_ikey(x))
    assert pub.all(lambda x: contains_prop_keys(x, "env", "app"))


def test_simple_logging(sut: Tuple[AppInsightsTelemetry, MockPublisher]):
    ait, pub = sut
    tag = "a1"
    with ait:
        lgr = ait.root
        lgr.debug(f"debug in {tag}")
        lgr.info(f"info in {tag}")
        lgr.warn(f"warn in {tag}")
        lgr.error(f"error in {tag}")
        lgr.critical(f"critical in {tag}", god="Quetzalcoatl")
    assert pub.count() == 5
    assert pub.all(lambda x: is_trace(x))
    assert pub.all(lambda x: tag in x.data.baseData.message)
    assert pub.last(lambda x: contains_prop(x, "god", "Quetzalcoatl"))
    _assert(pub)


def test_exception(sut: Tuple[AppInsightsTelemetry, MockPublisher]):
    ait, pub = sut
    with ait:
        try:
            func_raise_error()
        except ZeroDivisionError as e:
            ait.root.exception(e)

    assert pub.count() == 1
    assert pub.all(lambda x: is_exception(x))
    _assert(pub)


def test_metrics(sut: Tuple[AppInsightsTelemetry, MockPublisher]):
    ait, pub = sut
    with ait:
        m1 = ait.metric_incr("m1")
        m2 = ait.metric_extra("m2", {"group": "Alpha"})
        m1()
        m1()
        m2(42, {"devil": 666})
    assert pub.count() == 3
    assert pub.all(lambda x: is_metric(x))
    assert pub.last(lambda x: contains_prop_keys(x, "group", "devil"))
    _assert(pub)


def test_activity_on_success(sut: Tuple[AppInsightsTelemetry, MockPublisher]):
    ait, pub = sut
    with ait:
        with ait.activity("act1"):
            time.sleep(0.6)
    assert pub.count() == 2
    assert pub.all(lambda x: is_metric(x))
    assert pub.all(lambda x: contains_prop(x, "activity", "act1"))
    assert pub.all(lambda x: contains_prop_keys(x, "activity_id"))
    assert pub.any(lambda x: contains_datapoint(x, "act1_ok"))
    assert pub.any(lambda x: contains_datapoint(x, "act1_ms"))
    _assert(pub)


def test_activity_on_error(sut: Tuple[AppInsightsTelemetry, MockPublisher]):
    ait, pub = sut
    with pytest.raises(ZeroDivisionError):
        with ait:
            with ait.activity("act2"):
                time.sleep(0.3)
                func_raise_error()
    assert pub.count(lambda x: is_metric(x)) == 2
    assert pub.count(lambda x: is_exception(x)) == 1
    assert pub.all(lambda x: contains_prop(x, "activity", "act2"))
    assert pub.all(lambda x: contains_prop_keys(x, "activity_id"))
    assert pub.any(lambda x: contains_datapoint(x, "act2_err"))
    assert pub.any(lambda x: contains_datapoint(x, "act2_ms"))
    _assert(pub)
