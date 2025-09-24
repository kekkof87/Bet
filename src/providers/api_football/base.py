from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class FixturesProviderBase(ABC):
    @abstractmethod
    def fetch_fixtures(
        self,
        date: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError