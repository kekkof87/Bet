from __future__ import annotations

from typing import Dict, List, Tuple

from .models import FixtureDataset, FixtureRecord


def index_by_id(fixtures: FixtureDataset) -> Dict[int, FixtureRecord]:
    out: Dict[int, FixtureRecord] = {}
    for f in fixtures:
        fid = f.get("fixture_id")
        if isinstance(fid, int):
            out[fid] = f
    return out


def diff_fixtures(
    old: FixtureDataset, new: FixtureDataset
) -> Tuple[List[int], List[int], List[int]]:
    old_idx = index_by_id(old)
    new_idx = index_by_id(new)
    old_ids = set(old_idx.keys())
    new_ids = set(new_idx.keys())
    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    potentially_modified = old_ids & new_ids
    modified: List[int] = []
    for fid in potentially_modified:
        if old_idx[fid] != new_idx[fid]:
            modified.append(fid)
    return added, removed, modified
