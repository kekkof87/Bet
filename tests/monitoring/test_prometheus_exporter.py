import json
from pathlib import Path

from prometheus_client import CollectorRegistry
from monitoring.prometheus_exporter import update_prom_metrics, generate_prometheus_text, _REGISTRY
from core.config import _reset_settings_cache_for_tests


def test_update_prometheus_metrics(monkeypatch, tmp_path):
    # Setup env
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_PROMETHEUS_EXPORTER", "1")
    _reset_settings_cache_for_tests()

    data_dir = Path(tmp_path)
    metrics_dir = data_dir / "metrics"
    events_dir = data_dir / "events"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)

    # metrics/last_run.json
    (metrics_dir / "last_run.json").write_text(
        json.dumps(
            {
                "summary": {"added": 1, "removed": 0, "modified": 2, "total_new": 50},
                "change_breakdown": {"score_change": 2, "status_change": 1, "both": 0, "other": 0},
                "fetch_stats": {"attempts": 1, "retries": 0, "latency_ms": 123.4, "last_status": 200},
                "total_fixtures": 50,
            }
        ),
        encoding="utf-8",
    )

    # events/last_delta.json
    (events_dir / "last_delta.json").write_text(
        json.dumps(
            {
                "added": [{"fixture_id": 10}],
                "removed": [],
                "modified": [{"fixture_id": 11}, {"fixture_id": 12}],
                "change_breakdown": {"score_change": 1, "status_change": 0, "both": 0, "other": 0},
            }
        ),
        encoding="utf-8",
    )

    # scoreboard.json
    (data_dir / "scoreboard.json").write_text(
        json.dumps({"live_count": 3, "upcoming_count_next_24h": 5}), encoding="utf-8"
    )

    # Esegue update
    update_prom_metrics()

    # Ottiene testo
    output = generate_prometheus_text().decode("utf-8")
    # Verifiche base
    assert "bet_fetch_runs_total" in output
    assert "bet_fixtures_total" in output
    assert "bet_delta_added" in output
    assert "bet_scoreboard_live" in output
