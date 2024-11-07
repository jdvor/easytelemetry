#!/usr/bin/env python

import pyperf
from shared import sample_envelope

import easytelemetry.appinsights.protocol as p


def main():
    envelope = sample_envelope()

    runner = pyperf.Runner()
    runner.timeit(
        name="serialize envelope",
        stmt="p.serialize(envelope)",
        globals={"envelope": envelope, "p": p},
    )


if __name__ == "__main__":
    main()
