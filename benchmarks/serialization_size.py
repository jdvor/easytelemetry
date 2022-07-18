import gzip

from shared import sample_envelope

from easytelemetry.appinsights.protocol import serialize


def compress(payload: bytes) -> bytes:
    return gzip.compress(payload, compresslevel=6)


for i in range(1, 7):
    upper = 2 if i == 1 else (i * i) + 1
    envelopes = [sample_envelope() for j in range(1, upper)]
    original = serialize(envelopes)
    compressed = compress(original)
    pct = round(100 * len(compressed) / len(original), 1)
    print(
        f"n: {len(envelopes)}, original: {len(original)} B"
        + f", compressed: {pct}% ({len(compressed)} B)"
    )
