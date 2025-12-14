from typing import List, Dict, Optional, Tuple
from .fuzzy import fuzzy_matcher
from .cache import item_cache
from utils.database import get_item, search_items as db_search_items, get_all_items_for_game
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
        
        items = await get_all_items_for_game(game, limit=1000)
        if not items:
            return None
        
        norm_query = self.normalize(query)
        
        for item in items:
            item_norm = item.get('normalized_name', self.normalize(item.get('name', '')))
            item_id = item.get('item_id', '').lower()
            if item_norm == norm_query or item_id == norm_query:
                result = self._format_item(item)
                await item_cache.set(cache_key, result)
                return result
        
        game_aliases = self._item_aliases.get(game, {})
        if norm_query in game_aliases:
            alias_target = game_aliases[norm_query]
            for item in items:
                item_norm = item.get('normalized_name', self.normalize(item.get('name', '')))
                item_id = item.get('item_id', '').lower()
                if item_norm == alias_target or item_id == alias_target:
                    result = self._format_item(item)
                    await item_cache.set(cache_key, result)
                    return result
        
        item_names = [item['name'] for item in items]
        match = fuzzy_matcher.best_match(query, item_names)
        
        if match and match[1] <= 2:
            for item in items:
                if item['name'] == match[0]:
                    result = self._format_item(item)
                    await item_cache.set(cache_key, result)
                    return result
        
        return None
    
    def _format_item(self, item: Dict) -> Dict:
        metadata = {}
        if item.get('metadata'):
            try:
                if isinstance(item['metadata'], str):
                    metadata = json.loads(item['metadata'])
                else:
                    metadata = item['metadata']
            except:
                pass
        
        return {
            'id': item.get('item_id', ''),
            'name': item.get('name', ''),
            'normalized_name': item.get('normalized_name', ''),
            'rarity': item.get('rarity', 'Unknown'),
            'icon_url': item.get('icon_url'),
            'value': float(item.get('value', 0)),
            'tradeable': bool(item.get('tradeable', True)),
            'game': item.get('game', ''),
            'metadata': metadata
        }
    
    async def search_items(self, game: str, query: str, limit: int = 10) -> List[Dict]:
        items = await get_all_items_for_game(game, limit=1000)
        if not items:
            return []
        
        norm_query = self.normalize(query)
        
        exact_matches = []
        partial_matches = []
        fuzzy_matches = []
        
        for item in items:
            item_norm = item.get('normalized_name', self.normalize(item.get('name', '')))
            if item_norm == norm_query:
                exact_matches.append((item, 0))
            elif norm_query in item_norm:
                partial_matches.append((item, 1))
            else:
                dist = fuzzy_matcher.distance(query, item['name'])
                if dist <= 3:
                    fuzzy_matches.append((item, dist + 2))
        
        all_matches = exact_matches + partial_matches + fuzzy_matches
        all_matches.sort(key=lambda x: x[1])
        
        return [self._format_item(m[0]) for m in all_matches[:limit]]
    
    async def suggest_items(self, game: str, query: str, limit: int = 3) -> List[Dict]:
        return await self.search_items(game, query, limit)
    
    async def validate_item(self, game: str, item_id: str) -> bool:
        item = await get_item(game, item_id)
        return item is not None
    
    async def get_item_value(self, game: str, item_id: str) -> Optional[float]:
        item = await get_item(game, item_id)
        if item:
            return float(item.get('value', 0))
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
