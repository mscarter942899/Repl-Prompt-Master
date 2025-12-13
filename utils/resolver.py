from typing import List, Dict, Optional, Tuple
from api.base import APIRegistry
from .fuzzy import fuzzy_matcher
from .cache import item_cache
import json

class ItemResolver:
    GAME_ALIASES = {
        'ps99': ['pet simulator 99', 'petsim99', 'petsim', 'ps'],
        'gag': ['grow a garden', 'growagraden', 'garden'],
        'am': ['adopt me', 'adoptme'],
        'bf': ['blox fruits', 'bloxfruits', 'bloxfruit'],
        'sab': ['steal a brainrot', 'stealabrainrot', 'brainrot']
    }
    
    def __init__(self):
        self._item_aliases: Dict[str, Dict[str, str]] = {}
    
    def normalize(self, text: str) -> str:
        return text.lower().replace(' ', '').replace('-', '').replace('_', '').replace("'", '')
    
    def resolve_game(self, query: str) -> Optional[str]:
        norm_query = self.normalize(query)
        
        for game, aliases in self.GAME_ALIASES.items():
            if norm_query == game or norm_query in [self.normalize(a) for a in aliases]:
                return game
        
        return None
    
    async def resolve_item(self, game: str, query: str) -> Optional[Dict]:
        cache_key = f"resolve:{game}:{self.normalize(query)}"
        cached = await item_cache.get(cache_key)
        if cached:
            return cached
        
        adapter = APIRegistry.get(game)
        if not adapter:
            return None
        
        items = await adapter.fetch_items()
        if not items:
            return None
        
        norm_query = self.normalize(query)
        
        for item in items:
            if item['normalized_name'] == norm_query or item['id'].lower() == norm_query:
                await item_cache.set(cache_key, item)
                return item
        
        game_aliases = self._item_aliases.get(game, {})
        if norm_query in game_aliases:
            alias_target = game_aliases[norm_query]
            for item in items:
                if item['normalized_name'] == alias_target or item['id'].lower() == alias_target:
                    await item_cache.set(cache_key, item)
                    return item
        
        item_names = [item['name'] for item in items]
        match = fuzzy_matcher.best_match(query, item_names)
        
        if match and match[1] <= 2:
            for item in items:
                if item['name'] == match[0]:
                    await item_cache.set(cache_key, item)
                    return item
        
        return None
    
    async def search_items(self, game: str, query: str, limit: int = 10) -> List[Dict]:
        adapter = APIRegistry.get(game)
        if not adapter:
            return []
        
        items = await adapter.fetch_items()
        if not items:
            return []
        
        norm_query = self.normalize(query)
        
        exact_matches = []
        partial_matches = []
        fuzzy_matches = []
        
        for item in items:
            if item['normalized_name'] == norm_query:
                exact_matches.append((item, 0))
            elif norm_query in item['normalized_name']:
                partial_matches.append((item, 1))
            else:
                dist = fuzzy_matcher.distance(query, item['name'])
                if dist <= 3:
                    fuzzy_matches.append((item, dist + 2))
        
        all_matches = exact_matches + partial_matches + fuzzy_matches
        all_matches.sort(key=lambda x: x[1])
        
        return [m[0] for m in all_matches[:limit]]
    
    async def suggest_items(self, game: str, query: str, limit: int = 3) -> List[Dict]:
        return await self.search_items(game, query, limit)
    
    async def validate_item(self, game: str, item_id: str) -> bool:
        adapter = APIRegistry.get(game)
        if not adapter:
            return False
        
        item = await adapter.fetch_item(item_id)
        return item is not None
    
    async def get_item_value(self, game: str, item_id: str) -> Optional[float]:
        adapter = APIRegistry.get(game)
        if not adapter:
            return None
        
        item = await adapter.fetch_item(item_id)
        if item:
            return item.get('value', 0)
        return None
    
    def register_alias(self, game: str, alias: str, target: str) -> None:
        if game not in self._item_aliases:
            self._item_aliases[game] = {}
        self._item_aliases[game][self.normalize(alias)] = self.normalize(target)
    
    async def calculate_trade_value(self, game: str, items: List[str]) -> float:
        total = 0.0
        for item_id in items:
            value = await self.get_item_value(game, item_id)
            if value:
                total += value
        return total


item_resolver = ItemResolver()
