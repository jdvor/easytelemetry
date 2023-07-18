from datetime import timedelta
import time
import uuid

import pytest

from easytelemetry.appinsights import Options
import easytelemetry.appinsights.protocol as p


@pytest.mark.integration
def test_serialize_trace(options: Options):
    url = options.connection.ingestion_endpoint
    batch = [create_trace(options)]
    result = p.send_batch(batch, url, gzip_threshold=-1, max_attempts=0)
    assert result.success


@pytest.mark.integration
def test_serialize_metric(options: Options):
    url = options.connection.ingestion_endpoint
    batch = [create_metric(options)]
    result = p.send_batch(batch, url, gzip_threshold=-1, max_attempts=0)
    assert result.success


@pytest.mark.integration
def test_serialize_event(options: Options):
    url = options.connection.ingestion_endpoint
    batch = [create_event(options)]
    result = p.send_batch(batch, url, gzip_threshold=-1, max_attempts=0)
    assert result.success


@pytest.mark.integration
def test_serialize_dependency(options: Options):
    url = options.connection.ingestion_endpoint
    batch = [create_dependency(options)]
    result = p.send_batch(batch, url, gzip_threshold=-1, max_attempts=0)
    assert result.success


@pytest.mark.integration
def test_serialize_request(options: Options):
    url = options.connection.ingestion_endpoint
    batch = [create_request(options)]
    result = p.send_batch(batch, url, gzip_threshold=-1, max_attempts=0)
    assert result.success


@pytest.mark.integration
def test_serialize_exception(options: Options):
    url = options.connection.ingestion_endpoint
    batch = [create_exception(options)]
    result = p.send_batch(batch, url, gzip_threshold=-1, max_attempts=0)
    assert result.success


@pytest.mark.integration
def test_serialize_gzip_encoding(options: Options):
    url = options.connection.ingestion_endpoint
    batch = [create_trace(options)]
    result = p.send_batch(batch, url, gzip_threshold=10, max_attempts=0)
    assert result.success


def create_trace(options: Options) -> p.Envelope:
    envelope = p.MessageData(
        message="lorem ipsum dolor sit",
        severityLevel=p.SeverityLevel.INFORMATION,
        properties={"alpha": "1", "beta": "2"},
    ).to_envelope()
    enrich_envelope(envelope, options.connection.instrumentation_key)
    return envelope


def create_metric(options: Options) -> p.Envelope:
    envelope = p.MetricData.create(
        name="update_user_ms",
        value=176,
        properties={"alpha": "1"},
    ).to_envelope()
    enrich_envelope(envelope, options.connection.instrumentation_key)
    return envelope


def create_event(options: Options) -> p.Envelope:
    envelope = p.EventData(
        name="UserLoggedIn",
        properties={"alpha": "1"},
        measurements={"elapsed_ms": 12.5, "payload_size": 878},
    ).to_envelope()
    enrich_envelope(envelope, options.connection.instrumentation_key)
    return envelope


def create_dependency(options: Options) -> p.Envelope:
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
    enrich_envelope(envelope, options.connection.instrumentation_key)
    return envelope


def create_request(options: Options) -> p.Envelope:
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
    enrich_envelope(envelope, options.connection.instrumentation_key)
    return envelope


def func_raise_error() -> None:
    """Raise ZeroDivisionError"""
    _ = 1 / 0


def create_exception(options: Options) -> p.Envelope:
    try:
        func_raise_error()
    except ZeroDivisionError as ex:
        envelope = p.ExceptionData.create(
            ex,
            p.SeverityLevel.ERROR,
            properties={"alpha": "1"},
            measurements={"elapsed_ms": 278},
        ).to_envelope()
        enrich_envelope(envelope, options.connection.instrumentation_key)
        return envelope
    else:
        assert False, "this should not happen"  # noqa: PT015


def enrich_envelope(e: p.Envelope, ikey: str) -> None:
    e.iKey = ikey
    e.seq = str(time.time_ns() // 1_000_000)
    e.tags = {
        p.TagKey.OPERATION_ID: str(uuid.uuid4()),
        p.TagKey.OPERATION_PARENT_ID: "0d96cb1c-38d2-41ed-9ffd-801c0862049c",
        p.TagKey.CLOUD_ROLE_INSTANCE: "LIEN-02",
        p.TagKey.LOCATION_IP: "94.230.174.81",
        p.TagKey.APP_VER: "1.0.1",
    }
