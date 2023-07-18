from datetime import timedelta
import json
import time
import uuid

import pytest
from utils import func_raise_error

import easytelemetry.appinsights.protocol as p


IS_SAFE_KEY_DATA = [
    ("alpha", True, ""),
    ("BETA", True, ""),
    ("alpha_ext", True, ""),
    ("beta9", True, ""),
    ("", False, "empty"),
    ("  ", False, "whitespace"),
    ("8flake", False, "starts with number"),
    (r"lorem\da", False, "unsafe characters"),
    (r"lorem$", False, "unsafe characters"),
    ("a" * (p.MAX_KEY_LENGTH + 1), False, "too long"),
]


@pytest.mark.parametrize(("test", "expected", "msg"), IS_SAFE_KEY_DATA)
def test_is_safe_key(test: str, expected: bool, msg: str):
    actual = p.is_safe_key(test)
    assert expected == actual, msg


def test_serialize_trace():
    envelope = p.MessageData(
        message="lorem ipsum dolor sit",
        severityLevel=p.SeverityLevel.INFORMATION,
        properties={"alpha": "1", "beta": "2"},
    ).to_envelope()
    enrich_envelope(envelope)
    js = envelope.to_json()
    assert is_valid_json(js)
    assert p.Envelope.TRACE_NAME in js


def test_serialize_metric():
    envelope = p.MetricData.create(
        name="update_user_ms",
        value=176,
        properties={"alpha": "1"},
    ).to_envelope()
    enrich_envelope(envelope)
    js = envelope.to_json()
    assert is_valid_json(js)
    assert p.Envelope.METRIC_NAME in js


def test_serialize_event():
    envelope = p.EventData(
        name="UserLoggedIn",
        properties={"alpha": "1"},
        measurements={"elapsed_ms": 12.5, "payload_size": 878},
    ).to_envelope()
    enrich_envelope(envelope)
    js = envelope.to_json()
    assert is_valid_json(js)
    assert p.Envelope.EVENT_NAME in js


def test_serialize_dependency():
    envelope = p.RemoteDependencyData(
        name="user_posts",
        duration=timedelta(milliseconds=1281),
        success=True,
        id="posts/user/1584",
        data=r"posts WHERE user = @user_id",
        target="datalake1.example.com",
        type="SQL",
        properties={"alpha": "1"},
    ).to_envelope()
    enrich_envelope(envelope)
    js = envelope.to_json()
    assert is_valid_json(js)
    assert p.Envelope.DEPENDENCY_NAME in js


def test_serialize_request():
    envelope = p.RequestData(
        id=f"posts/user/1584:{uuid.uuid4()}",
        duration=timedelta(milliseconds=54),
        responseCode="200 OK",
        success=True,
        name="posts/user/{id}",
        source="94.230.174.81",
        url="https://api.example.com/posts/4895",
        properties={"alpha": "1"},
        measurements={"elapsed_ms": 121},
    ).to_envelope()
    enrich_envelope(envelope)
    js = envelope.to_json()
    assert is_valid_json(js)
    assert p.Envelope.REQUEST_NAME in js


def test_serialize_exception():
    try:
        func_raise_error()
    except ZeroDivisionError as ex:
        envelope = p.ExceptionData.create(
            ex,
            p.SeverityLevel.ERROR,
            properties={"alpha": "1"},
            measurements={"elapsed_ms": 278},
        ).to_envelope()
        enrich_envelope(envelope)
        js = envelope.to_json()
        assert is_valid_json(js)
        assert p.Envelope.EXCEPTION_NAME in js
    else:
        assert False, "this should not happen"  # noqa: PT015


def is_valid_json(js: str) -> bool:
    obj = json.loads(js)
    has_name = obj.get("name") is not None
    has_time = obj.get("time") is not None
    has_data = obj.get("data") is not None
    return has_name and has_time and has_data


def enrich_envelope(e: p.Envelope) -> None:
    e.iKey = str(uuid.uuid4())
    e.seq = str(time.time_ns() // 1_000_000)
    e.tags = {
        p.TagKey.OPERATION_ID: str(uuid.uuid4()),
        p.TagKey.OPERATION_PARENT_ID: "0d96cb1c-38d2-41ed-9ffd-801c0862049c",
        p.TagKey.CLOUD_ROLE_INSTANCE: "LIEN-02",
        p.TagKey.LOCATION_IP: "94.230.174.81",
    }
