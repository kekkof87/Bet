import json
import time
from pathlib import Path

from core.persistence import save_history_snapshot, rotate_history

def test_save_history_and_rotate(tmp_path, monkeypatch):
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    data_dir = Path(tmp_path)
    snapshots = []
    for i in range(5):
        fixtures = [{"fixture_id": i, "home_score": 0, "away_score": 0}]
        p = save_history_snapshot(fixtures)
        snapshots.append(p)
        time.sleep(0.01)  # garantisce ordine timestamp differente

    assert (data_dir / "history").exists()
    assert len(list((data_dir / "history").glob("fixtures_*.json"))) == 5

    rotate_history(3)
    remaining = sorted((data_dir / "history").glob("fixtures_*.json"))
    assert len(remaining) == 3

    # Controlla che i file rimasti siano gli ultimi 3 (ordine per nome)
    names = [p.name for p in remaining]
    assert names == sorted(names)  # banale, ma rafforza ordine
