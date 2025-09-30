import time
from pathlib import Path

from core.persistence import save_history_snapshot, rotate_history


def test_save_history_and_rotate(tmp_path, monkeypatch):
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    data_dir = Path(tmp_path)

    # Crea 5 snapshot distinti
    created = []
    for i in range(5):
        fixtures = [{"fixture_id": i, "home_score": 0, "away_score": 0}]
        p = save_history_snapshot(fixtures)
        created.append(p)
        # micro-delay per rendere i timestamp ordinati anche se i microsecondi sono già inclusi
        time.sleep(0.001)

    history_dir = data_dir / "history"
    assert history_dir.exists(), "La cartella history non è stata creata"

    all_files = sorted(history_dir.glob("fixtures_*.json"))
    assert len(all_files) == 5, f"Attesi 5 snapshot, trovati {len(all_files)}: {all_files}"

    # Rotazione: mantieni solo gli ultimi 3
    rotate_history(3)
    remaining = sorted(history_dir.glob("fixtures_*.json"))
    assert len(remaining) == 3, f"Dopo rotazione attesi 3 snapshot, trovati {len(remaining)}"

    # Devono essere gli ultimi 3 alfabeticamente (che corrisponde ai più recenti)
    # Verifica che nessuno dei primi due originari rimanga, se i nomi sono tutti diversi
    if len({p.name for p in all_files}) == 5:  # solo se non ci sono collisioni
        dropped = {p.name for p in all_files[:-3]}
        remaining_names = {p.name for p in remaining}
        assert not dropped & remaining_names, "Alcuni snapshot vecchi non sono stati rimossi"
