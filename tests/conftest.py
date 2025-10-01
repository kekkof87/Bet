import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402
from core.config import _reset_settings_cache_for_tests  # noqa: E402


@pytest.fixture(autouse=True)
def reset_settings_cache():
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()
