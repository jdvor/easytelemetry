from __future__ import annotations

import pytest


@pytest.fixture()
def erroneous() -> Erroneous:
    return Erroneous()


class Erroneous:
    def divide_one_by(self, divider: int) -> float:
        return self._inner(divider)

    def _inner(self, divider: int) -> float:
        return 1 / divider
