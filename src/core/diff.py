from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Tuple, Literal

Fixture = Dict[str, Any]
ModifiedPair = Tuple[Fixture, Fixture]
ChangeType = Literal["score_change", "status_change", "both", "other"]

def _default_key(f: Fixture) -> Any:
    """
    Chiave primaria preferenziale: fixture_id; fallback: (league_id, date_utc, home_team, away_team).
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
            continue
        # Scarta chiave fallback incompleta (evita tuple con None multiple)
        if isinstance(k, tuple) and any(part is None for part in k):
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
    Diff basico (compat retro) – mantiene la firma originaria.
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

    for k in old_keys & new_keys:
        o = old_index[k]
        n = new_index[k]
        if compare_keys is None:
            if o != n:
                modified.append((o, n))
        else:
            for ck in compare_keys:
                if o.get(ck) != n.get(ck):
                    modified.append((o, n))
                    break

    return added, removed, modified

def _classify_change(o: Fixture, n: Fixture) -> ChangeType:
    score_changed = (o.get("home_score") != n.get("home_score")) or (o.get("away_score") != n.get("away_score"))
    status_changed = o.get("status") != n.get("status")
    if score_changed and status_changed:
        return "both"
    if score_changed:
        return "score_change"
    if status_changed:
        return "status_change"
    return "other"

def diff_fixtures_detailed(
    old: List[Fixture],
    new: List[Fixture],
    *,
    key_fn: Callable[[Fixture], Any] = _default_key,
    compare_keys: Iterable[str] | None = None,
    classify: bool = True,
) -> Dict[str, Any]:
    """
    Versione avanzata del diff con classificazione modifiche.

    Ritorna un dict:
    {
        "added": [...],
        "removed": [...],
        "modified": [
            {"old": {...}, "new": {...}, "change_type": "..."}
        ],
        "change_breakdown": {"score_change": X, "status_change": Y, "both": Z, "other": W}
    }
    """
    added, removed, modified_pairs = diff_fixtures(old, new, key_fn=key_fn, compare_keys=compare_keys)

    detailed: List[Dict[str, Any]] = []
    breakdown = {"score_change": 0, "status_change": 0, "both": 0, "other": 0}

    if classify:
        for o, n in modified_pairs:
            ctype = _classify_change(o, n)
            breakdown[ctype] += 1
            detailed.append({"old": o, "new": n, "change_type": ctype})
    else:
        for o, n in modified_pairs:
            detailed.append({"old": o, "new": n, "change_type": "other"})

    return {
        "added": added,
        "removed": removed,
        "modified": detailed,
        "change_breakdown": breakdown,
    }

def summarize_delta(
    added: List[Fixture],
    removed: List[Fixture],
    modified: List[ModifiedPair] | List[Dict[str, Any]],
    total_new: int,
) -> Dict[str, int]:
    # modified può essere lista di tuple o lista di dict (detailed)
    mod_len = len(modified)
    return {
        "added": len(added),
        "removed": len(removed),
        "modified": mod_len,
        "total_new": total_new,
    }

__all__ = [
    "diff_fixtures",
    "diff_fixtures_detailed",
    "summarize_delta",
]
