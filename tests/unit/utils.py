"""Utility methods for creating sample data for unit tests"""

from typing import Optional, Union

import easytelemetry.appinsights.protocol as p


def func_raise_error() -> None:
    """Raise ZeroDivisionError"""
    _ = 1 / 0


def contains_ikey(
    e: p.Envelope,
    ikey: str = "00000000-0000-0000-0000-000000000000",
) -> bool:
    return e.iKey == ikey


def is_trace(e: p.Envelope) -> bool:
    return e.data.baseType == "MessageData"


def is_exception(e: p.Envelope) -> bool:
    if e.data.baseType != "ExceptionData":
        return False
    exs = e.data.baseData.exceptions
    if len(exs) == 0:
        return False
    for ex in exs:
        if ex.parsedStack is None or len(ex.parsedStack) == 0:
            return False
    return True


def is_metric(e: p.Envelope) -> bool:
    return e.data.baseType == "MetricData"


def contains_prop(
    e: p.Envelope,
    key: str,
    value: Optional[Union[str, int, float, bool]] = None,
) -> bool:
    has_key = key in e.data.baseData.properties
    if not has_key:
        return False
    return (
        has_key if value is None else value == e.data.baseData.properties[key]
    )


def contains_prop_keys(e: p.Envelope, *args: str) -> bool:
    for key in args:
        if key not in e.data.baseData.properties:
            return False
    return True


def contains_datapoint(e: p.Envelope, name: str) -> bool:
    if not is_metric(e):
        return False
    md: p.MetricData = e.data.baseData
    return md.metrics[0].name == name
