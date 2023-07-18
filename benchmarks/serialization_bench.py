import pyperf
from shared import sample_envelope

import easytelemetry.appinsights.protocol as p


envelope = sample_envelope()

runner = pyperf.Runner()
runner.timeit(
    name="serialize envelope",
    stmt="p.serialize(envelope)",
    globals={"envelope": envelope, "p": p},
)
