import pytest
from core.config import _reset_settings_cache_for_tests
import os


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()
    for var in [
        "API_FOOTBALL_KEY",
        "API_FOOTBALL_DEFAULT_LEAGUE_ID",
        "API_FOOTBALL_DEFAULT_SEASON",
        "BET_LOG_LEVEL",
    ]:
        monkeypatch.delenv(var, raising=False)