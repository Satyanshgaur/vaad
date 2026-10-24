from __future__ import annotations

from datetime import date

import pytest

# Fixed reference date so relative-date tests ("kal", "parson") never depend on today.
REF_DATE = date(2026, 10, 24)


@pytest.fixture
def ref_date() -> date:
    return REF_DATE
