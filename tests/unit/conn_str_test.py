import pytest

from easytelemetry.appinsights import DEFAULT_INGESTION, ConnectionString


IKEY = "22a165b8-944e-4f74-9605-66e79223d0ac"
INGEST = "https://westeurope-5.in.applicationinsights.azure.com/"
INGEST_FULL = "https://westeurope-5.in.applicationinsights.azure.com/v2/track"
LIVE = "https://westeurope.livediagnostics.monitor.azure.com/"


def test_full_form():
    test = f"InstrumentationKey={IKEY};IngestionEndpoint={INGEST};LiveEndpoint={LIVE}"
    cs = ConnectionString.from_str(test)
    assert cs.instrumentation_key == IKEY
    assert cs.ingestion_endpoint == INGEST_FULL
    assert cs.live_endpoint == LIVE


def test_full_form_with_whitespace():
    test = f"InstrumentationKey={IKEY}; IngestionEndpoint={INGEST}; LiveEndpoint={LIVE}"
    cs = ConnectionString.from_str(test)
    assert cs.instrumentation_key == IKEY
    assert cs.ingestion_endpoint == INGEST_FULL
    assert cs.live_endpoint == LIVE


def test_legacy_form():
    test = f"InstrumentationKey={IKEY};IngestionEndpoint={INGEST}"
    cs = ConnectionString.from_str(test)
    assert cs.instrumentation_key == IKEY
    assert cs.ingestion_endpoint == INGEST_FULL
    assert cs.live_endpoint is None


def test_only_instrumentation_key():
    cs = ConnectionString.from_str(IKEY)
    assert cs.instrumentation_key == IKEY
    assert cs.ingestion_endpoint == DEFAULT_INGESTION
    assert cs.live_endpoint is None


INVALID_CONNECTION_STRINGS = [
    "",
    "   ",
    "loremipsum",
]


@pytest.mark.parametrize("test", INVALID_CONNECTION_STRINGS)
def test_invalid_strings(test: str):
    with pytest.raises(ValueError, match="invalid connection string"):
        ConnectionString.from_str(test)
