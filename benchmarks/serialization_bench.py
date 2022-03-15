import pyperf
from shared import sample_envelope

envelope = sample_envelope()

runner = pyperf.Runner()
runner.timeit(
    name='to_json_bytes',
    stmt='envelope.to_json_bytes()',
    globals={'envelope': envelope},
)
