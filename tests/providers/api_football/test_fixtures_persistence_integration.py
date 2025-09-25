import json
import pytest

from core.config import _reset_settings_cache_for_tests
from core.persistence import LATEST_FIXTURES_FILE

# Adatta questo import al tuo path reale
from providers.api_football.fixtures_provider import APIFootballFixturesProvider
from providers.api_football.http_client import _client_singleton


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY_KEY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    _reset_settings_cache_for_tests()
    global _client_singleton
    _client_singleton = None
    yield
    _reset_settings_cache_for_tests()
    _client_singleton = None


def test_persistence_enabled(monkeypatch):
    class FakeClient:
        def api_get(self, path, params=None):
            return {"response": [{"id": 10}, {"id": 11}]}

    monkeypatch.setenv("API_FOOTBALL_PERSIST_FIXTURES", "true")
    monkeypatch.setattr(
        "providers.api_football.fixtures_provider.get_http_client",
        lambda: FakeClient(),
    )
    provider = APIFootballFixturesProvider()
    fixtures = provider.fetch_fixtures()
    assert len(fixtures) == 2
    assert LATEST_FIXTURES_FILE.exists()
    data = json.loads(LATEST_FIXTURES_FILE.read_text(encoding="utf-8"))
    assert data == fixtures


def test_persistence_disabled(monkeypatch):
    class FakeClient:
        def api_get(self, path, params=None):
            return {"response": [{"id": 90}]}

    monkeypatch.setenv("API_FOOTBALL_PERSIST_FIXTURES", "false")
    monkeypatch.setattr(
        "providers.api_football.fixtures_provider.get_http_client",
        lambda: FakeClient(),
    )
    provider = APIFootballFixturesProvider()
    fixtures = provider.fetch_fixtures()
    assert fixtures and fixtures[0]["id"] == 90
    assert not LATEST_FIXTURES_FILE.exists()
