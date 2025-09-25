import json
from pathlib import Path

from core.persistence import (
    save_latest_fixtures,
    load_latest_fixtures,
    LATEST_FIXTURES_FILE,
)


def test_load_missing_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    assert load_latest_fixtures() == []


def test_save_and_load_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    data = [{"id": 1, "name": "Match A"}, {"id": 2, "name": "Match B"}]
    save_latest_fixtures(data)
    assert LATEST_FIXTURES_FILE.exists()
    loaded = load_latest_fixtures()
    assert loaded == data


def test_save_skips_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    save_latest_fixtures([])
    assert not LATEST_FIXTURES_FILE.exists()


def test_invalid_json_returns_empty_and_warn(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    target = Path(tmp_path) / "fixtures_latest.json"
    target.write_text("{not-valid-json", encoding="utf-8")
    out = load_latest_fixtures()
    assert out == []
    warnings = [r for r in caplog.messages if "invalid" in r.lower() or "corrupt" in r.lower()]
    assert warnings


def test_non_list_structure_returns_empty_and_warn(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    target = Path(tmp_path) / "fixtures_latest.json"
    target.write_text(json.dumps({"a": 1}), encoding="utf-8")
    out = load_latest_fixtures()
    assert out == []
    assert any("invalid structure" in m.lower() for m in caplog.messages)
