import json
from pathlib import Path
import pytest

from predictions.value_history import append_value_history
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_VALUE_HISTORY", "1")
    monkeypatch.setenv("VALUE_HISTORY_MODE", "rolling")
    monkeypatch.setenv("VALUE_HISTORY_MAX_FILES", "2")
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_value_history_append_and_rotate(tmp_path: Path):
    alerts = [
        {
            "source": "prediction",
            "value_type": "prediction_value",
            "fixture_id": 10,
            "value_side": "home_win",
            "value_edge": 0.06,
            "model_version": "baseline-v1",
        },
        {
            "source": "consensus",
            "value_type": "consensus_value",
            "fixture_id": 10,
            "value_side": "home_win",
            "value_edge": 0.04,
        },
    ]
    # First append
    append_value_history(alerts)
    # Second append (simulate new run)
    append_value_history(alerts)
    # Third append triggers rotation (max 2)
    append_value_history(alerts)

    vh_dir = tmp_path / "value_history"
    files = sorted(vh_dir.glob("value_history_*.jsonl"))
    assert len(files) <= 2
    # Each file should have at least two lines
    for f in files:
        content_lines = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(content_lines) >= 2
        # Line JSON parse check
        for ln in content_lines:
            obj = json.loads(ln)
            assert "fixture_id" in obj
            assert "value_edge" in obj
