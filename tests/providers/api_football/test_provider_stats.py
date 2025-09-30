import pytest

from providers.api_football.fixtures_provider import ApiFootballFixturesProvider
from core.config import _reset_settings_cache_for_tests


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = {}
        self.text = ""

    def json(self):
        return self._json_data


def build_sequence(responses):
    it = iter(responses)

    def _get(url, params=None, timeout=None):
        item = next(it)
        if isinstance(item, Exception):
            raise item
        return item

    return _get


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_fetch_stats_success_no_retry(monkeypatch):
    payload = {
        "response": [
            {
                "fixture": {"id": 1, "date": "2025-09-30T10:00:00Z", "status": {"short": "NS"}},
                "league": {"id": 100, "season": 2025},
                "teams": {"home": {"name": "A"}, "away": {"name": "B"}},
                "goals": {"home": None, "away": None},
            }
        ]
    }
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence([FakeResponse(200, payload)]),
    )
    provider = ApiFootballFixturesProvider()
    fixtures = provider.fetch_fixtures()
    assert len(fixtures) == 1
    stats = provider.get_last_stats()
    assert stats["attempts"] == 1
    assert stats["retries"] == 0
    assert stats["last_status"] == 200
    assert stats["latency_ms"] >= 0.0


def test_fetch_stats_with_retry(monkeypatch):
    payload_ok = {
        "response": [
            {
                "fixture": {"id": 2, "date": "2025-09-30T11:00:00Z", "status": {"short": "NS"}},
                "league": {"id": 101, "season": 2025},
                "teams": {"home": {"name": "C"}, "away": {"name": "D"}},
                "goals": {"home": 0, "away": 0},
            }
        ]
    }
    seq = [
        FakeResponse(500, {"error": "temp"}),
        FakeResponse(200, payload_ok),
    ]
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence(seq),
    )
    provider = ApiFootballFixturesProvider()
    fixtures = provider.fetch_fixtures()
    assert len(fixtures) == 1
    stats = provider.get_last_stats()
    assert stats["attempts"] == 2
    assert stats["retries"] == 1
    assert stats["last_status"] == 200


def test_fetch_stats_rate_limit_exhausted(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_MAX_ATTEMPTS", "2")
    _reset_settings_cache_for_tests()

    seq = [
        FakeResponse(429, {"error": "rate"}),
        FakeResponse(429, {"error": "rate"}),
    ]
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence(seq),
    )
    provider = ApiFootballFixturesProvider()
    with pytest.raises(Exception):
        provider.fetch_fixtures()
    stats = provider.get_last_stats()
    assert stats["attempts"] == 2
    assert stats["retries"] == 1
    assert stats["last_status"] == 429
