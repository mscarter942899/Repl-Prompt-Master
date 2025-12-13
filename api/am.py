from typing import List, Dict, Optional
import json
import os
from .base import GameAPIAdapter, APIRegistry

class AdoptMeAdapter(GameAPIAdapter):
    def __init__(self):
        super().__init__('am')
        self.fallback_path = 'data/fallback_am.json'
        
    async def fetch_items(self) -> List[Dict]:
        cached = self._get_cached('items')
        if cached:
            return cached
        
        return self._load_fallback()
    
    async def fetch_item(self, item_id: str) -> Optional[Dict]:
        items = await self.fetch_items()
        for item in items:
            if item['id'] == item_id or item['normalized_name'] == item_id.lower():
                return item
        return None
    
    async def fetch_values(self) -> Dict[str, float]:
        items = await self.fetch_items()
        return {item['id']: item['value'] for item in items}
    
    async def fetch_icons(self) -> Dict[str, str]:
        items = await self.fetch_items()
        return {item['id']: item['icon_url'] for item in items if item.get('icon_url')}
    
    async def health_check(self) -> bool:
        items = await self.fetch_items()
        return len(items) > 0
    
    def normalize_item(self, item: Dict) -> Dict:
        item_id = str(item.get('id', item.get('name', '')))
        name = item.get('name', 'Unknown')
        
        rarity_map = {
            'common': 'Common',
            'uncommon': 'Uncommon',
            'rare': 'Rare',
            'ultra-rare': 'Ultra Rare',
            'legendary': 'Legendary'
        }
        rarity = rarity_map.get(item.get('rarity', '').lower(), 'Common')
        
        return {
            'id': item_id,
            'name': name,
            'normalized_name': self._normalize_name(name),
            'rarity': rarity,
            'icon_url': item.get('icon', ''),
            'value': float(item.get('value', 0)),
            'tradeable': item.get('tradeable', True),
            'game': self.game_name,
            'metadata': {
                'category': item.get('category', 'pet'),
                'neon': item.get('neon', False),
                'mega_neon': item.get('mega_neon', False),
                'flyable': item.get('flyable', False),
                'rideable': item.get('rideable', False)
            }
        }
    
    def _load_fallback(self) -> List[Dict]:
        if os.path.exists(self.fallback_path):
            try:
                with open(self.fallback_path, 'r') as f:
                    data = json.load(f)
                    items = [self.normalize_item(item) for item in data.get('items', [])]
                    self._set_cached('items', items)
                    return items
            except:
                pass
        return []

def setup():
    APIRegistry.register('am', AdoptMeAdapter())
