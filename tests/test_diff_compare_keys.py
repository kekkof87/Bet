from core.diff import diff_fixtures


def test_diff_with_compare_keys_limits_modified() -> None:
    old = [
        {"fixture_id": 1, "home_score": 0, "away_score": 0, "status": "NS", "note": "A"},
    ]
    new = [
        # Cambia solo "note": non deve risultare modified con compare_keys limitate
        {"fixture_id": 1, "home_score": 0, "away_score": 0, "status": "NS", "note": "B"},
    ]
    added, removed, modified = diff_fixtures(old, new, compare_keys=["home_score", "away_score", "status"])
    assert added == []
    assert removed == []
    assert modified == []


def test_diff_with_compare_keys_detects_score_change() -> None:
    old = [
        {"fixture_id": 10, "home_score": 0, "away_score": 0, "status": "NS"},
    ]
    new = [
        {"fixture_id": 10, "home_score": 1, "away_score": 0, "status": "NS"},
    ]
    added, removed, modified = diff_fixtures(old, new, compare_keys=["home_score", "away_score", "status"])
    assert len(modified) == 1
