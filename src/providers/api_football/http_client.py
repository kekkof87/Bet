from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from core.config import get_settings
from core.logging import get_logger
from .exceptions import RateLimitError, TransientAPIError

log = get_logger(__name__)

_BASE_URL = "https://v3.football.api-sports.io"


class APIFootballHttpClient:
    """
    Client HTTP con retry e backoff per API Football (versione requests).
    Gestisce rate limit (429), errori transitori (5xx, network) e ritorna JSON.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "x-apisports-key": self._settings.api_football_key,
                "Accept": "application/json",
            }
        )
        self._max_attempts = self._settings.api_football_max_attempts
       
