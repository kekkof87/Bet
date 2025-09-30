from core.diff import diff_fixtures_detailed

def test_diff_classification_score_change():
    old = [{"fixture_id": 1, "home_score": 0, "away_score": 0, "status": "NS"}]
    new = [{"fixture_id": 1, "home_score": 1, "away_score": 0, "status": "NS"}]
    out = diff_fixtures_detailed(old, new, classify=True)
    assert out["change_breakdown"]["score_change"] == 1
    assert out["change_breakdown"]["status_change"] == 0
    assert len(out["modified"]) == 1
    assert out["modified"][0]["change_type"] == "score_change"

def test_diff_classification_status_change():
    old = [{"fixture_id": 2, "home_score": 0, "away_score": 0, "status": "NS"}]
    new = [{"fixture_id": 2, "home_score": 0, "away_score": 0, "status": "1H"}]
    out = diff_fixtures_detailed(old, new, classify=True)
    assert out["change_breakdown"]["status_change"] == 1
    assert out["modified"][0]["change_type"] == "status_change"

def test_diff_classification_both():
    old = [{"fixture_id": 3, "home_score": 0, "away_score": 0, "status": "NS"}]
    new = [{"fixture_id": 3, "home_score": 1, "away_score": 0, "status": "1H"}]
    out = diff_fixtures_detailed(old, new, classify=True)
    assert out["change_breakdown"]["both"] == 1
    assert out["modified"][0]["change_type"] == "both"

def test_diff_classification_other():
    # Cambia un campo fuori dallo scope (es: note) -> se compare_keys non limita, compare shallow => modified
    old = [{"fixture_id": 4, "home_score": 0, "away_score": 0, "status": "NS", "note": "A"}]
    new = [{"fixture_id": 4, "home_score": 0, "away_score": 0, "status": "NS", "note": "B"}]
    out = diff_fixtures_detailed(old, new, classify=True)
    # Il cambiamento non tocca punteggio o status -> other
    assert out["change_breakdown"]["other"] == 1
    assert out["modified"][0]["change_type"] == "other"
