from __future__ import annotations

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

    Flusso:
      1. Carica snapshot precedente (latest) se presente.
      2. Fetch nuove fixtures dal provider.
      3. Calcola delta (added / removed / modified).
      4. Se esistevano dati precedenti -> salva snapshot previous.
      5. Salva nuove fixtures come latest.
      6. Logga un riepilogo dei conteggi delta + esempio prima fixture.

    Nota:
      - Il provider httpx (ApiFootballFixturesProvider) NON salva di suo; la persistenza
        avviene qui esplicitamente.
      - Se vuoi limitare il confronto a certe chiavi (es. punteggi) puoi modificare la
        chiamata a diff_fixtures aggiungendo compare_keys=[...].
    """
    logger = get_logger("scripts.fetch_fixtures")

    try:
        settings = get_settings()
    except ValueError as e:
        logger.error(str(e))
        logger.error(
            "Aggiungi API_FOOTBALL_KEY nel file .env oppure come variabile ambiente."
        )
        return

    # 1. Snapshot precedente
    old = load_latest_fixtures()
    logger.info("Avvio fetch fixtures (API-Football)...")

    # 2. Fetch nuove fixtures
    provider = ApiFootballFixturesProvider()
    new = provider.fetch_fixtures(
        league_id=settings.default_league_id,
        season=settings.default_season,
        date=None,
    )

    # 3. Calcolo delta
    added, removed, modified = diff_fixtures(old, new)

    # 4. Salva snapshot previous (solo se c'era qualcosa prima)
    if old:
        try:
            save_previous_fixtures(old)
        except Exception as exc:
            logger.error("Errore salvataggio snapshot previous: %s", exc)

    # 5. Salva nuovo stato (se non vuoto — opzionale, puoi salvare anche vuoto se preferisci pulire)
    try:
        save_latest_fixtures(new)
    except Exception as exc:
        logger.error("Errore salvataggio fixtures latest: %s", exc)

    # 6. Logging riepilogo delta
    summary = summarize_delta(added, removed, modified, len(new))
    logger.info("fixtures_delta %s", summary)

    if new:
        logger.info("Esempio prima fixture: %s", new[0])


if __name__ == "__main__":
    main()
