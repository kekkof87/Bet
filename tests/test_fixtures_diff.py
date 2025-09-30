from core.diff import diff_fixtures, summarize_delta


def test_diff_added_removed_modified() -> None:
    old = [
        {"fixture_id": 1, "home_score": 0, "away_score": 0, "status": "NS"},
        {"fixture_id": 2, "home_score": 1, "away_score": 0, "status": "1H"},
        {"fixture_id": 3, "home_score": 2, "away_score": 2, "status": "FT"},
    ]
    new = [
        # fixture_id=1 modificata
        {"fixture_id": 1, "home_score": 1, "away_score": 0, "status": "1H"},
        # fixture_id=2 rimossa
        # fixture_id=3 invariata
        {"fixture_id": 3, "home_score": 2, "away_score": 2, "status": "FT"},
        # fixture_id=4 aggiunta
        {"fixture_id": 4, "home_score": 0, "away_score": 0, "status": "NS"},
    ]

    added, removed, modified = diff_fixtures(old, new)
    assert {f["fixture_id"] for f in added} == {4}
    assert {f["fixture_id"] for f in removed} == {2}
    assert [pair[0]["fixture_id"] for pair in modified] == [1]  # modificata solo 1

    summary = summarize_delta(added, removed, modified, len(new))
    assert summary == {
        "added": 1,
        "removed": 1,
        "modified": 1,
        "total_new": 3 + 1 - 1,  # oppure len(new) = 3 (id 1,3,4)
    }


def test_diff_no_changes() -> None:
    base = [
        {"fixture_id": 10, "home_score": 0, "away_score": 0, "status": "NS"},
        {"fixture_id": 11, "home_score": 1, "away_score": 0, "status": "1H"},
    ]
    added, removed, modified = diff_fixtures(base, [*base])
    assert added == []
    assert removed == []
    assert modified == []


def test_diff_without_fixture_id_fallback_key() -> None:
    old = [
        {
            "league_id": 100,
            "date_utc": "2025-01-01T10:00:00Z",
            "home_team": "Alpha",
            "away_team": "Beta",
            "home_score": 0,
            "away_score": 0,
        }
    ]
    new = [
        {
            "league_id": 100,
            "date_utc": "2025-01-01T10:00:00Z",
            "home_team": "Alpha",
            "away_team": "Beta",
            "home_score": 1,  # score cambiato
            "away_score": 0,
        }
    ]
    added, removed, modified = diff_fixtures(old, new)
    assert added == []
    assert removed == []
    assert len(modified) == 1
