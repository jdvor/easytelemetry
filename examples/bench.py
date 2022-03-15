import uuid

import requests

import easytelemetry.appinsights.protocol as p

ikey = "42f6354d-d622-4979-bd92-a313c027e7d9"
ingestion_url = "https://westeurope-1.in.applicationinsights.azure.com/v2/track"
default_ingestion_url = "https://dc.services.visualstudio.com/v2/track"


class Erroneous:
    def divide_one_by(self, divider: int) -> float:
        return self._inner(divider)

    def _inner(self, divider: int) -> float:
        return 1 / divider


def enrich_envelope(e: p.Envelope) -> None:
    e.iKey = str(uuid.uuid4())
    e.seq = "1"
    e.tags = {
        p.TagKey.OPERATION_ID: str(uuid.uuid4()),
        p.TagKey.OPERATION_PARENT_ID: "0d96cb1c-38d2-41ed-9ffd-801c0862049c",
        p.TagKey.CLOUD_ROLE_INSTANCE: "LIEN-02",
        p.TagKey.LOCATION_IP: "94.230.174.81",
    }


def serialize_exception() -> str:
    try:
        erroneous = Erroneous()
        erroneous.divide_one_by(0)
    except ZeroDivisionError as ex:
        envelope = p.create_exception(
            ex,
            p.SeverityLevel.ERROR,
            props={"alpha": "1"},
            measurements={"elapsed_ms": 278},
        )
        enrich_envelope(envelope)
        return envelope.to_json()
    else:
        assert False, "this should not happen"  # noqa: PT015


body1 = serialize_exception()
body1_bytes = body1.strip().encode("utf-8")
resp = requests.post(
    url=ingestion_url,
    data=body1_bytes,
    headers={"Content-Type": "application/json"},
    timeout=5,
)

print(f"{resp.status_code=}")
print(f"{resp.content=}")
print("\nDONE")
