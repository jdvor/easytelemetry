from __future__ import annotations

import pytest
from easytelemetry.appinsights.impl import Options
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env')


@pytest.fixture()
def options() -> Options:
    return Options.from_env('intgtests')


@pytest.fixture()
def erroneous() -> Erroneous:
    return Erroneous()


class Erroneous:
    def divide_one_by(self, divider: int) -> float:
        return self._inner(divider)

    def _inner(self, divider: int) -> float:
        return 1 / divider
