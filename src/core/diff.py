from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Tuple


Fixture = Dict[str, Any]
ModifiedPair = Tuple[Fixture, Fixture]


def _default_key(f: Fixture) -> Any:
    """
    Ritorna la chiave primaria di una fixture.
    Preferenza:
      1. fixture_id
      2. (league_id, date_utc, home_team, away_team) come fallback
    """
    if "fixture_id" in f and f.get("fixture_id") is not None:
        return f.get("fixture_id")
    return (
        f.get("league_id"),
        f.get("date_utc"),
        f.get("home_team"),
        f.get("away_team"),
    )


def _index(fixtures: Iterable[Fixture], key_fn: Callable[[Fixture], Any]) -> Dict[Any, Fixture]:
    idx: Dict[Any, Fixture] = {}
    for item in fixtures:
        try:
            k = key_fn(item)
        except Exception:
            # Se la key function esplode, salta quell'elemento
            continue
        if k is not None:
            idx[k] = item
    return idx


def diff_fixtures(
    old: List[Fixture],
    new: List[Fixture],
    *,
    key_fn: Callable[[Fixture], Any] = _default_key,
    compare_keys: Iterable[str] | None = None,
) -> Tuple[List[Fixture], List[Fixture], List[ModifiedPair]]:
    """
    Calcola il delta tra due insiemi di fixtures.

    Ritorna:
        added:   fixture presenti solo in new
        removed: fixture presenti solo in old
        modified: lista di tuple (old_fixture, new_fixture) con stessa chiave ma contenuto diverso

    compare_keys:
        Se specificato, limita il confronto a queste chiavi (es: ["home_score", "away_score", "status"]).
        Se None confronta l'intero dict (shallow equality).
    """
    if not old and not new:
        return [], [], []

    old_index = _index(old, key_fn)
    new_index = _index(new, key_fn)

    added: List[Fixture] = []
    removed: List[Fixture] = []
    modified: List[ModifiedPair] = []

    old_keys = set(old_index.keys())
    new_keys = set(new_index.keys())

    for k in new_keys - old_keys:
        added.append(new_index[k])
    for k in old_keys - new_keys:
        removed.append(old_index[k])

    # Confronto modifiche (intersezione)
    for k in old_keys & new_keys:
        o = old_index[k]
        n = new_index[k]
        if compare_keys is None:
            if o != n:
                modified.append((o, n))
        else:
            # Confronto limitato alle chiavi indicare
            changed = False
            for ck in compare_keys:
                if o.get(ck) != n.get(ck):
                    changed = True
                    break
            if changed:
                modified.append((o, n))

    return added, removed, modified


def summarize_delta(
    added: List[Fixture],
    removed: List[Fixture],
    modified: List[ModifiedPair],
    total_new: int,
) -> Dict[str, int]:
    return {
        "added": len(added),
        "removed": len(removed),
        "modified": len(modified),
        "total_new": total_new,
    }
