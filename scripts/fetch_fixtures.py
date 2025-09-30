from __future__ import annotations

from typing import Any, Dict, List

from core.config import get_settings
from core.diff import diff_fixtures, summarize_delta
from core.logging import get_logger
from core.persistence import (
    load_latest_fixtures,
    save_latest_fixtures,
    save_previous_fixtures,
)
from providers.api_football.fixtures_provider import ApiFootballFixturesProvider


def main() -> None:
    """
    Fetch delle fixtures dal provider API-Football con calcolo delta.

    Passi:
      1. Carica snapshot precedente (latest).
      2. Fetch nuove fixtures dal provider.
      3. Calcola delta (added / removed / modified).
      4. Salva snapshot previous (se esisteva uno stato).
      5. Salva nuove fixtures (latest).
      6. Logga riepilogo delta + esempio.

    NOTE:
      - Per limitare il confronto a certe chiavi (es. punteggi):
        diff_fixtures(old, new, compare_keys=["home_score","away_score","status"])
      - Anche se new è vuoto viene salvato (stato corrente = nessun dato).
    """
    logger = get_logger("scripts.fetch_fixtures")

    # Config
    try:
        settings = get_settings()
    except ValueError as e:
        logger.error("%s", e)
        logger.error(
            "Aggiungi API_FOOTBALL_KEY nel file .env oppure come variabile ambiente."
        )
        return

    # 1. Carica snapshot precedente
    old: List[Dict[str, Any]] = load_latest_fixtures()
    if not isinstance(old, list):
        logger.warning("Snapshot precedente non è una lista valida, proseguo con old=[]")
        old = []

    logger.info("Avvio fetch fixtures (API-Football)...")

    # 2. Fetch nuove fixtures
    provider = ApiFootballFixturesProvider()
    new: List[Dict[str, Any]] = provider.fetch_fixtures(
        league_id=settings.default_league_id,
        season=settings.default_season,
        date=None,
    )
    if not isinstance(new, list):
        logger.error(
            "Provider ha restituito un oggetto non lista (%s). Abort diff.",
            type(new),
        )
        new = []

    # 3. Calcolo delta (protetto)
    try:
        added, removed, modified = diff_fixtures(old, new)
    except Exception as exc:  # pragma: no cover (difensivo)
        logger.error("Errore durante il diff fixtures: %s", exc)
        added, removed, modified = [], [], []

    # 4. Salvataggio snapshot previous (solo se c'era uno stato non vuoto)
    if old:
        try:
            save_previous_fixtures(old)
        except Exception as exc:  # pragma: no cover
            logger.error("Errore salvataggio snapshot previous: %s", exc)

    # 5. Salvataggio nuovo stato (anche vuoto)
    try:
        save_latest_fixtures(new)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore salvataggio fixtures latest: %s", exc)

    # 6. Logging riepilogo delta
    summary = summarize_delta(added, removed, modified, len(new))
    logger.info("fixtures_delta: %s", summary)

    if new:
        logger.info("Esempio prima fixture: %s", new[0])
    else:
        logger.info("Nessuna fixture ottenuta.")


if __name__ == "__main__":
    main()
