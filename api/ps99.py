from typing import List, Dict, Optional
import json
import os
from .base import GameAPIAdapter, APIRegistry

class PS99Adapter(GameAPIAdapter):
    def __init__(self):
        super().__init__('ps99')
        self.base_url = 'https://biggamesapi.io/api'
        self.fallback_path = 'data/fallback_ps99.json'
        
    async def fetch_items(self) -> List[Dict]:
        cached = self._get_cached('items')
        if cached:
            return cached
            
        data = await self._request(f'{self.base_url}/collection/Pets')
        if data and 'data' in data:
            items = [self.normalize_item(item) for item in data['data']]
            self._set_cached('items', items)
            return items
        
        return self._load_fallback()
    
    async def fetch_item(self, item_id: str) -> Optional[Dict]:
        items = await self.fetch_items()
        for item in items:
            if item['id'] == item_id or item['normalized_name'] == item_id.lower():
                return item
        return None
    
    async def fetch_values(self) -> Dict[str, float]:
        cached = self._get_cached('values')
        if cached:
            return cached
            
        data = await self._request(f'{self.base_url}/rap')
        if data and 'data' in data:
            values = {}
            for item in data['data']:
                if 'configData' in item and 'value' in item:
                    pet_id = item['configData'].get('id', '')
                    if pet_id:
                        values[pet_id] = float(item['value'])
            self._set_cached('values', values)
            return values
        
        return {}
    
    async def fetch_icons(self) -> Dict[str, str]:
        items = await self.fetch_items()
        return {item['id']: item['icon_url'] for item in items if item.get('icon_url')}
    
    async def health_check(self) -> bool:
        try:
            data = await self._request(f'{self.base_url}/collection/Pets')
            return data is not None and 'data' in data
        except:
            return False
    
    def normalize_item(self, item: Dict) -> Dict:
        config = item.get('configData', {})
        pet_id = config.get('id', str(item.get('_id', '')))
        name = config.get('name', item.get('configName', 'Unknown'))
        
        huge = config.get('huge', False)
        titanic = config.get('titanic', False)
        
        rarity = 'Common'
        if titanic:
            rarity = 'Titanic'
        elif huge:
            rarity = 'Huge'
        elif config.get('legendary'):
            rarity = 'Legendary'
        elif config.get('epic'):
            rarity = 'Epic'
        elif config.get('rare'):
            rarity = 'Rare'
            
        thumbnail = config.get('thumbnail', '')
        if thumbnail and not thumbnail.startswith('http'):
            thumbnail = f'https://biggamesapi.io/image/{thumbnail}'
        
        return {
            'id': pet_id,
            'name': name,
            'normalized_name': self._normalize_name(name),
            'rarity': rarity,
            'icon_url': thumbnail,
            'value': float(item.get('value', 0)),
            'tradeable': config.get('tradeable', True),
            'game': self.game_name,
            'metadata': {
                'huge': huge,
                'titanic': titanic,
                'golden': config.get('golden', False),
                'rainbow': config.get('rainbow', False),
                'shiny': config.get('shiny', False)
            }
        }
    
    def _load_fallback(self) -> List[Dict]:
        if os.path.exists(self.fallback_path):
            try:
                with open(self.fallback_path, 'r') as f:
                    data = json.load(f)
                    return [self.normalize_item({'configData': item}) for item in data.get('items', [])]
            except:
                pass
        return []

def setup():
    APIRegistry.register('ps99', PS99Adapter())
