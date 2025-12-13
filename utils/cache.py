from typing import Any, Optional, Dict
from datetime import datetime, timedelta
import hashlib
import json
import asyncio

class Cache:
    def __init__(self, default_ttl: int = 1800):
        self._cache: Dict[str, Any] = {}
        self._expiry: Dict[str, datetime] = {}
        self._default_ttl = timedelta(seconds=default_ttl)
        self._lock = asyncio.Lock()
    
    def _generate_key(self, *args, **kwargs) -> str:
        key_data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key in self._cache:
                if datetime.now() < self._expiry.get(key, datetime.min):
                    return self._cache[key]
                else:
                    del self._cache[key]
                    if key in self._expiry:
                        del self._expiry[key]
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> None:
        async with self._lock:
            self._cache[key] = value
            expiry_time = timedelta(seconds=ttl) if ttl else self._default_ttl
            self._expiry[key] = datetime.now() + expiry_time
    
    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._expiry:
                    del self._expiry[key]
                return True
            return False
    
    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
            self._expiry.clear()
    
    async def cleanup_expired(self) -> int:
        async with self._lock:
            now = datetime.now()
            expired = [k for k, v in self._expiry.items() if v < now]
            for key in expired:
                del self._cache[key]
                del self._expiry[key]
            return len(expired)
    
    def cached(self, ttl: int = None):
        def decorator(func):
            async def wrapper(*args, **kwargs):
                key = f"{func.__name__}:{self._generate_key(*args, **kwargs)}"
                cached_value = await self.get(key)
                if cached_value is not None:
                    return cached_value
                result = await func(*args, **kwargs)
                await self.set(key, result, ttl)
                return result
            return wrapper
        return decorator
    
    @property
    def size(self) -> int:
        return len(self._cache)


class IconCache(Cache):
    def __init__(self):
        super().__init__(default_ttl=604800)
        self._hash_map: Dict[str, str] = {}
    
    def _generate_icon_hash(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16]
    
    async def get_icon(self, item_id: str, game: str) -> Optional[str]:
        key = f"icon:{game}:{item_id}"
        return await self.get(key)
    
    async def set_icon(self, item_id: str, game: str, url: str) -> None:
        key = f"icon:{game}:{item_id}"
        icon_hash = self._generate_icon_hash(url)
        self._hash_map[key] = icon_hash
        await self.set(key, url)
    
    async def verify_icon(self, item_id: str, game: str, url: str) -> bool:
        key = f"icon:{game}:{item_id}"
        stored_hash = self._hash_map.get(key)
        if not stored_hash:
            return False
        return stored_hash == self._generate_icon_hash(url)


item_cache = Cache(default_ttl=1800)
icon_cache = IconCache()
user_cache = Cache(default_ttl=300)
