from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio

class RateLimiter:
    def __init__(self, requests_per_minute: int = 30, requests_per_hour: int = 300):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self._minute_buckets: Dict[int, Dict[str, int]] = {}
        self._hour_buckets: Dict[int, Dict[str, int]] = {}
        self._lock = asyncio.Lock()
    
    def _get_minute_key(self) -> int:
        now = datetime.now()
        return int(now.timestamp() // 60)
    
    def _get_hour_key(self) -> int:
        now = datetime.now()
        return int(now.timestamp() // 3600)
    
    async def check(self, user_id: int, action: str = 'default') -> tuple[bool, Optional[int]]:
        async with self._lock:
            key = f"{user_id}:{action}"
            minute_key = self._get_minute_key()
            hour_key = self._get_hour_key()
            
            if minute_key not in self._minute_buckets:
                self._minute_buckets = {minute_key: {}}
            if hour_key not in self._hour_buckets:
                self._hour_buckets = {hour_key: {}}
            
            minute_count = self._minute_buckets[minute_key].get(key, 0)
            hour_count = self._hour_buckets[hour_key].get(key, 0)
            
            if minute_count >= self.requests_per_minute:
                retry_after = 60 - (datetime.now().second)
                return False, retry_after
            
            if hour_count >= self.requests_per_hour:
                retry_after = 3600 - (datetime.now().minute * 60 + datetime.now().second)
                return False, retry_after
            
            self._minute_buckets[minute_key][key] = minute_count + 1
            self._hour_buckets[hour_key][key] = hour_count + 1
            
            return True, None
    
    async def get_remaining(self, user_id: int, action: str = 'default') -> Dict[str, int]:
        async with self._lock:
            key = f"{user_id}:{action}"
            minute_key = self._get_minute_key()
            hour_key = self._get_hour_key()
            
            minute_count = self._minute_buckets.get(minute_key, {}).get(key, 0)
            hour_count = self._hour_buckets.get(hour_key, {}).get(key, 0)
            
            return {
                'minute_remaining': max(0, self.requests_per_minute - minute_count),
                'hour_remaining': max(0, self.requests_per_hour - hour_count)
            }
    
    async def reset(self, user_id: int, action: str = 'default') -> None:
        async with self._lock:
            key = f"{user_id}:{action}"
            for bucket in self._minute_buckets.values():
                if key in bucket:
                    del bucket[key]
            for bucket in self._hour_buckets.values():
                if key in bucket:
                    del bucket[key]


class ActionCooldown:
    def __init__(self):
        self._cooldowns: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def set_cooldown(self, user_id: int, action: str, seconds: int) -> None:
        async with self._lock:
            key = f"{user_id}:{action}"
            self._cooldowns[key] = datetime.now() + timedelta(seconds=seconds)
    
    async def check_cooldown(self, user_id: int, action: str) -> tuple[bool, Optional[int]]:
        async with self._lock:
            key = f"{user_id}:{action}"
            if key not in self._cooldowns:
                return True, None
            
            if datetime.now() >= self._cooldowns[key]:
                del self._cooldowns[key]
                return True, None
            
            remaining = int((self._cooldowns[key] - datetime.now()).total_seconds())
            return False, remaining
    
    async def clear_cooldown(self, user_id: int, action: str) -> None:
        async with self._lock:
            key = f"{user_id}:{action}"
            if key in self._cooldowns:
                del self._cooldowns[key]


rate_limiter = RateLimiter()
action_cooldown = ActionCooldown()
