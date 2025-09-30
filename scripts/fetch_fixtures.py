from core.config import get_settings
from core.logging import get_logger
from providers.api_football.fixtures_provider import ApiFootballFixturesProvider


def main() -> None:
    """
    Script di fetch delle fixtures dal provider API-Football.
    Usa configurazione da get_settings() e logga un breve riepilogo.
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

    logger.info("Avvio fetch fixtures (API-Football)...")

    provider = ApiFootballFixturesProvider()
    fixtures = provider.fetch_fixtures(
        league_id=settings.default_league_id,
        season=settings.default_season,
        date=None,
    )

    logger.info("Fetch completato: %d fixtures", len(fixtures))
    if fixtures:
        logger.info("Esempio prima fixture: %s", fixtures[0])


if __name__ == "__main__":
    main()
