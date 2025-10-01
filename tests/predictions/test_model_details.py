from predictions.model import BaselineModel


def test_baseline_extremes_and_draw_floor():
    model = BaselineModel(version="baseline-v1")

    features = [
        # diff molto positivo -> home spinge verso clamp (0.7)
        {"fixture_id": 1, "score_diff": 20},
        # diff molto negativo -> away clamp 0.7
        {"fixture_id": 2, "score_diff": -20},
        # diff che forza draw quasi a zero per attivare correzione draw minimo
        {"fixture_id": 3, "score_diff": 5},
        # score_diff non numerico -> fallback diff=0
        {"fixture_id": 4, "score_diff": "N/A"},
    ]

    preds = model.predict(features)
    p_map = {p["fixture_id"]: p for p in preds}

    # fixture 1: home vicino o uguale a 0.7
    assert 0.69 <= p_map[1]["prob"]["home_win"] <= 0.7
    # fixture 2: away clamp
    assert 0.69 <= p_map[2]["prob"]["away_win"] <= 0.7
    # fixture 3: draw non scende sotto 0.05
    assert p_map[3]["prob"]["draw"] >= 0.05
    # fixture 4: diff non numerico -> baseline quasi invariata
    total4 = round(sum(p_map[4]["prob"].values()), 5)
    assert total4 == 1.0
