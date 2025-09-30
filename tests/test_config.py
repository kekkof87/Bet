import pytest

from core.config import get_settings, _reset_settings_cache_for_tests


def test_missing_api_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    _reset_settings_cache_for_tests()
    with pytest.raises(ValueError) as exc:
        get_settings()
    assert "API_FOOTBALL_KEY" in str(exc.value)


def test_present_api_key_ok(monkeypatch) -> None:
    monkeypatch.setenv("API_FOOTBALL_KEY", "TEST_KEY")
    _reset_settings_cache_for_tests()
    s = get_settings()
    assert s.api_football_key == "TEST_KEY"
