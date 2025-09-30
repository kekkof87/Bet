from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class FixturesProviderBase(ABC):
    """
    Interfaccia astratta per un provider di fixtures.

    Implementazioni concrete devono restituire una lista di dict (records delle fixtures)
    con almeno gli identificativi minimi necessari a distinguere una fixture.
    """

    @abstractmethod
    def fetch_fixtures(
        self,
        date: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Recupera le fixtures dal provider.

        Parametri:
            date: (opzionale) data in formato YYYY-MM-DD per filtrare.
            league_id: (opzionale) ID della lega.
            season: (opzionale) stagione (anno intero, es: 2024).

        Ritorna:
            Lista di dizionari (fixture records).
        """
        raise NotImplementedError
