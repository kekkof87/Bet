from core.alerts import build_alerts


def test_build_alerts_score_and_status():
    modified = [
        {
            "old": {"fixture_id": 10, "home_score": 0, "away_score": 0, "status": "NS"},
            "new": {"fixture_id": 10, "home_score": 1, "away_score": 0, "status": "1H"},
            "change_type": "both",
        },
        {
            "old": {"fixture_id": 11, "home_score": 1, "away_score": 0, "status": "1H"},
            "new": {"fixture_id": 11, "home_score": 1, "away_score": 1, "status": "1H"},
            "change_type": "score_change",
        },
        {
            "old": {"fixture_id": 12, "home_score": 2, "away_score": 1, "status": "HT"},
            "new": {"fixture_id": 12, "home_score": 2, "away_score": 1, "status": "2H"},
            "change_type": "status_change",
        },
        {
            # Transizione retrograda (non dovrebbe generare status_transition)
            "old": {"fixture_id": 13, "home_score": 0, "away_score": 0, "status": "2H"},
            "new": {"fixture_id": 13, "home_score": 0, "away_score": 0, "status": "1H"},
            "change_type": "status_change",
        },
    ]
    alerts = build_alerts(modified)
    # fixture_id 10: score_update + status_transition
    # fixture_id 11: score_update
    # fixture_id 12: status_transition
    # fixture_id 13: nessun status_transition (retrogrado), nessun score change
    types = [a["type"] for a in alerts]
    assert types.count("score_update") == 2
    assert types.count("status_transition") == 2
    # Verifica contenuti base
    score_alert = next(a for a in alerts if a["type"] == "score_update" and a["fixture_id"] == 10)
    assert score_alert["old_score"] == "0-0"
    assert score_alert["new_score"] == "1-0"
