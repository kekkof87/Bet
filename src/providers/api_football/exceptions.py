class RateLimitError(Exception):
    """Sollevata quando viene superato il rate limit (HTTP 429) dopo tutti i tentativi di retry."""


class TransientAPIError(Exception):
    """Sollevata quando errori transitori (5xx / timeout / connessione) persistono oltre i tentativi massimi."""
