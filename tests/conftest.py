import sys
from pathlib import Path

# Assicura che 'src' sia nel PYTHONPATH prima di importare i moduli
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.config import _reset_settings_cache_for_tests  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def reset_settings_cache():
    # Evita leakage tra test
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()
