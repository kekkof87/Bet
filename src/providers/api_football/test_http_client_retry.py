import types
import json
import pytest
import requests

from providers.api_football.http_client import get_http_client, _client_singleton
from providers.api_football.exceptions import RateLimitError, TransientAPIError
from core.config import _reset_settings_cache_for_tests


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.headers = headers or {}
        self.text = text or (json.dumps(json_data) if isinstance(json_data, (dict, list)) else "")

    def json(self):
        if self._json_data is None:
            raise ValueError("Invalid JSON")
        return self._json_data


@pytest.fixture(autouse=True)
def clean_singleton(monkeypatch):
    # Reset client & settings between test
    global _client_singleton
    _client_singleton = None
    _reset_settings_cache_for_tests()
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY_KEY")
    yield
    _client_singleton = None
    _reset_settings_cache_for_tests()


@pytest.fixture
def no_sleep(monkeypatch):
    calls = []

    def fake_sleep(seconds):
        calls.append(seconds)

    monkeypatch.setattr("providers.api_football.http_client.time.sleep", fake_sleep)
    return calls


@pytest.fixture
def fixed_jitter(monkeypatch):
    # Jitter deterministico = 1.0 (nessuna variazione)
    monkeypatch.setattr("providers.api_football.http_client.random.uniform", lambda a, b: 1.0)


def build_sequence_get(responses):
    """Ritorna una funzione get che restituisce in sequenza i FakeResponse o solleva eccezioni."""
    iterator = iter(responses)

    def _get(url, params=None, timeout=None):
        item = next(iterator)
        if isinstance(item, Exception):
            raise item
        return item

    return _get


def test_success_immediato(monkeypatch, fixed_jitter):
    resp = FakeResponse(200, {"ok": True})
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence_get([resp]),
    )
    client = get_http_client()
    out = client.api_get("/fixtures")
    assert out == {"ok": True}


def test_retry_su_500_poi_successo(monkeypatch, fixed_jitter, no_sleep):
    seq = [
        FakeResponse(500, {"error": "temp"}),
        FakeResponse(200, {"result": 42}),
    ]
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence_get(seq),
    )
    client = get_http_client()
    out = client.api_get("/fixtures")
    assert out["result"] == 42
    # Un retry => una sleep registrata
    assert len(no_sleep) == 1
    assert no_sleep[0] > 0  # delay calcolato


def test_retry_429_honor_retry_after(monkeypatch, fixed_jitter, no_sleep):
    # Retry-After = 1, computed base=0.5 -> 0.5 < 1 => atteso wait >= 1
    monkeypatch.setenv("API_FOOTBALL_BACKOFF_BASE", "0.5")
    seq = [
        FakeResponse(429, {"error": "rate"}, headers={"Retry-After": "1"}),
        FakeResponse(200, {"done": True}),
    ]
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence_get(seq),
    )
    client = get_http_client()
    out = client.api_get("/fixtures")
    assert out["done"] is True
    assert len(no_sleep) == 1
    assert no_sleep[0] >= 1.0


def test_rate_limit_esaurito(monkeypatch, fixed_jitter, no_sleep):
    # 3 tentativi configurati per testare più velocemente
    monkeypatch.setenv("API_FOOTBALL_MAX_ATTEMPTS", "3")
    seq = [
        FakeResponse(429, {"error": "rate"}, headers={"Retry-After": "0.2"}),
        FakeResponse(429, {"error": "rate"}, headers={"Retry-After": "0.2"}),
        FakeResponse(429, {"error": "rate"}, headers={"Retry-After": "0.2"}),
    ]
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence_get(seq),
    )
    client = get_http_client()
    with pytest.raises(RateLimitError):
        client.api_get("/fixtures")
    # Due sleep (prima degli ultimi tentativi falliti)
    assert len(no_sleep) == 2


def test_transient_network_error(monkeypatch, fixed_jitter, no_sleep):
    seq = [
        requests.ConnectionError("boom"),
        requests.Timeout("slow"),
        FakeResponse(200, {"ok": True}),
    ]
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence_get(seq),
    )
    client = get_http_client()
    out = client.api_get("/fixtures")
    assert out["ok"] is True
    # Due retry => due sleep
    assert len(no_sleep) == 2


def test_transient_network_error_esaurito(monkeypatch, fixed_jitter, no_sleep):
    monkeypatch.setenv("API_FOOTBALL_MAX_ATTEMPTS", "2")
    seq = [
        requests.ConnectionError("boom"),
        requests.ConnectionError("boom"),
    ]
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence_get(seq),
    )
    client = get_http_client()
    with pytest.raises(TransientAPIError):
        client.api_get("/fixtures")
    assert len(no_sleep) == 1  # solo un'attesa tra i due tentativi


def test_fail_fast_404(monkeypatch, fixed_jitter, no_sleep):
    seq = [FakeResponse(404, {"error": "not found"})]
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence_get(seq),
    )
    client = get_http_client()
    with pytest.raises(ValueError):
        client.api_get("/fixtures")
    assert len(no_sleep) == 0  # nessun retry


def test_invalid_json(monkeypatch, fixed_jitter):
    # status 200 ma json invalido => RuntimeError
    resp = FakeResponse(200, None)  # _json_data=None => ValueError dentro json()
    monkeypatch.setattr(
        "providers.api_football.http_client.requests.Session.get",
        build_sequence_get([resp]),
    )
    client = get_http_client()
    with pytest.raises(RuntimeError):
        client.api_get("/fixtures")
