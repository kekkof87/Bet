from telegram.parser import (
    parse_messages,
    classify_message,
    extract_score,
    extract_status,
    extract_fixture_id,
)


def test_extract_score():
    assert extract_score("Goal! 2-1!!!") == (2, 1)
    assert extract_score("Parziale 10 - 0") == (10, 0)
    assert extract_score("No score here") == (None, None)


def test_extract_status():
    assert extract_status("HT ora") == "HT"
    assert extract_status("Fine FT!!!") == "FT"
    assert extract_status("Prima parte 1H dominata") == "1H"
    assert extract_status("Nessuno") is None


def test_extract_fixture_id():
    assert extract_fixture_id("fixture_id=12345 goal!") == 12345
    assert extract_fixture_id("fixture id: 678900 GOAL 1-0") == 678900
    # Heuristica numero lungo
    assert extract_fixture_id("Evento 55555 parziale 1-0") == 55555
    assert extract_fixture_id("Nessun id qui") is None


def test_classify_message():
    assert classify_message("GOAL 1-0 fixture_id=100") == "goal"
    assert classify_message("HT 1-0") == "status"
    assert classify_message("Score now 2 - 2") == "score_update"
    assert classify_message("Messaggio irrilevante") is None


def test_parse_messages_basic():
    messages = [
        "GOAL 1-0 fixture_id=200",
        "HT 1-0 fixture id: 200",
        "Score update 2-0 fixture_id=200",
        "Nessun evento",
    ]
    events = parse_messages(messages)
    types = [e["type"] for e in events]
    assert "goal" in types
    assert "status" in types
    assert "score_update" in types
    # L'ultimo messaggio viene ignorato
    assert len(events) == 3
