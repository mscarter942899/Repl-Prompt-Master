from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GameAPIAdapter(ABC):
    def __init__(self, game_name: str):
        self.game_name = game_name
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=30)
        self._rate_limit_remaining = 100
        self._rate_limit_reset = datetime.now()
        self.default_values_url: str = ''
        self.values_url: str = ''
        
    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self._cache:
            if datetime.now() < self._cache_expiry.get(key, datetime.min):
                return self._cache[key]
            else:
                del self._cache[key]
                if key in self._cache_expiry:
                    del self._cache_expiry[key]
        return None
    
    def _set_cached(self, key: str, value: Any, ttl: Optional[timedelta] = None):
        self._cache[key] = value
        self._cache_expiry[key] = datetime.now() + (ttl or self._cache_ttl)
    
    async def _request(self, url: str, method: str = 'GET', **kwargs) -> Optional[Dict]:
        try:
            session = await self.get_session()
            async with session.request(method, url, **kwargs) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"{self.game_name} API rate limited. Retry after {retry_after}s")
                    return None
                    
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"{self.game_name} API error: {response.status}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"{self.game_name} API timeout")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"{self.game_name} API client error: {e}")
            return None
        except Exception as e:
            logger.error(f"{self.game_name} API unexpected error: {e}")
            return None
    
    @abstractmethod
    async def fetch_items(self) -> List[Dict]:
        pass
    
    @abstractmethod
    async def fetch_item(self, item_id: str) -> Optional[Dict]:
        pass
    
    @abstractmethod
    async def fetch_values(self) -> Dict[str, float]:
        pass
    
    @abstractmethod
    async def fetch_icons(self) -> Dict[str, str]:
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        pass
    
    def normalize_item(self, item: Dict) -> Dict:
        return {
            'id': str(item.get('id', item.get('item_id', ''))),
            'name': item.get('name', 'Unknown'),
            'normalized_name': self._normalize_name(item.get('name', '')),
            'rarity': item.get('rarity', 'Common'),
            'icon_url': item.get('icon_url', item.get('icon', '')),
            'value': float(item.get('value', item.get('rap', 0))),
            'tradeable': item.get('tradeable', True),
            'game': self.game_name,
            'metadata': item.get('metadata', {})
        }
    
    def _normalize_name(self, name: str) -> str:
        return name.lower().replace(' ', '').replace('-', '').replace('_', '').replace("'", '')


class APIRegistry:
    _adapters: Dict[str, GameAPIAdapter] = {}
    
    @classmethod
    def register(cls, game: str, adapter: GameAPIAdapter):
        cls._adapters[game.lower()] = adapter
    
    @classmethod
    def get(cls, game: str) -> Optional[GameAPIAdapter]:
        return cls._adapters.get(game.lower())
    
    @classmethod
    def all(cls) -> Dict[str, GameAPIAdapter]:
        return cls._adapters
    
    @classmethod
    async def close_all(cls):
        for adapter in cls._adapters.values():
            await adapter.close()
    
    @classmethod
    async def health_check_all(cls) -> Dict[str, bool]:
        results = {}
        for game, adapter in cls._adapters.items():
            results[game] = await adapter.health_check()
        return results
