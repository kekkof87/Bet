import pytest
from core.config import get_settings

def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    with pytest.raises(ValueError) as exc:
        get_settings()
    assert "API_FOOTBALL_KEY" in str(exc.value)

def test_present_api_key_ok(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "TEST_KEY")
    s = get_settings()
    assert s.api_football_key == "TEST_KEY"