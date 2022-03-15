import pyperf
import gzip
from shared import sample_envelope
from easytelemetry.appinsights.protocol import serialize


def compress(payload: bytes) -> bytes:
    return gzip.compress(payload, compresslevel=6)


envelopes = [sample_envelope() for i in range(1, 10)]
runner = pyperf.Runner()

runner.timeit(
    name='serialize',
    stmt='serialize(envelopes)',
    globals={'envelopes': envelopes,
             'serialize': serialize},
)

runner.timeit(
    name='serialize_gzip',
    stmt='compress(serialize(envelopes))',
    globals={'envelopes': envelopes,
             'serialize': serialize,
             'compress': compress},
)
