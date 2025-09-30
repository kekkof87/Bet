import pytest

from providers.api_football.fixtures_provider import ApiFootballFixturesProvider


@pytest.fixture
def mock_http(monkeypatch):
    """
    Mock della GET usata dal provider unificato (requests.Session.get).
    Restituisce una risposta coerente con la struttura API-Football.
    """
    def fake_get(*args, **kwargs):
        class R:
            status_code = 200

            def json(self):
                return {
                    "response": [
                        {
                            "fixture": {
                                "id": 123,
                                "date": "2024-08-30T18:45:00+00:00",
                                "status": {"short": "NS"},
                            },
                            "league": {"id": 135, "season": 2024},
                            "teams": {
                                "home": {"name": "Team A"},
                                "away": {"name": "Team B"},
                            },
                            "goals": {"home": None, "away": None},
                        }
                    ]
                }

            @property
            def text(self):
                return str(self.json())

        return R()

    # Variabili d'ambiente richieste
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("API_FOOTBALL_DEFAULT_LEAGUE_ID", "135")
    monkeypatch.setenv("API_FOOTBALL_DEFAULT_SEASON", "2024")

    # Patch del client requests usato da APIFootballHttpClient
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        fake_get,
    )
    return fake_get


def test_fetch_fixtures_normalization(mock_http) -> None:
    provider = ApiFootballFixturesProvider()
    fixtures = provider.fetch_fixtures()
    assert len(fixtures) == 1
    f = fixtures[0]
    assert f["fixture_id"] == 123
    assert f["league_id"] == 135
    assert f["season"] == 2024
    assert f["provider"] == "api_football"
    assert f["status"] == "NS"
    assert f["home_team"] == "Team A"
    assert f["away_team"] == "Team B"
