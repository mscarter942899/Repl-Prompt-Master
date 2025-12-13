from typing import List, Dict, Optional
import json
import os
import re
from .base import GameAPIAdapter, APIRegistry

class PS99Adapter(GameAPIAdapter):
    def __init__(self):
        super().__init__('ps99')
        self.base_url = 'https://biggamesapi.io/api'
        self.values_url = 'https://petsimulatorvalues.com/values.php?category=all'
        self.fallback_path = 'data/fallback_ps99.json'
        self._cosmic_values: Dict[str, Dict] = {}
        
    def _parse_value_string(self, value_str: str) -> float:
        if not value_str:
            return 0.0
        value_str = str(value_str).strip().upper().replace(',', '')
        multiplier = 1.0
        if 'T' in value_str:
            multiplier = 1_000_000_000_000
            value_str = value_str.replace('T', '')
        elif 'B' in value_str:
            multiplier = 1_000_000_000
            value_str = value_str.replace('B', '')
        elif 'M' in value_str:
            multiplier = 1_000_000
            value_str = value_str.replace('M', '')
        elif 'K' in value_str:
            multiplier = 1_000
            value_str = value_str.replace('K', '')
        try:
            return float(value_str) * multiplier
        except:
            return 0.0
    
    async def _fetch_cosmic_values(self) -> Dict[str, Dict]:
        cached = self._get_cached('cosmic_values')
        if cached:
            return cached
        
        try:
            session = await self.get_session()
            async with session.get(self.values_url) as response:
                if response.status != 200:
                    return {}
                html = await response.text()
                
            values = {}
            pet_blocks = re.findall(
                r'RAP:\s*([\d.,]+[TMBK]?).*?EXIST:\s*([\d,]+).*?'
                r'img[^>]*src="([^"]*)".*?'
                r'\*\*([^*]+)\*\*.*?'
                r'Variant([A-Za-z]+).*?'
                r'Value[^|]*\|\\?\s*([\d.,]+[TMBK]?).*?'
                r'Demand(\d+)/10',
                html,
                re.DOTALL | re.IGNORECASE
            )
            
            for match in pet_blocks:
                rap, exist, icon, name, variant, value, demand = match
                name = name.strip()
                normalized = self._normalize_name(name)
                
                values[normalized] = {
                    'name': name,
                    'value': self._parse_value_string(value),
                    'rap': self._parse_value_string(rap),
                    'exist': int(exist.replace(',', '')) if exist else 0,
                    'demand': int(demand) if demand else 5,
                    'variant': variant.strip() if variant else 'Normal',
                    'icon_url': icon if icon.startswith('http') else f'https://petsimulatorvalues.com{icon}'
                }
            
            if values:
                self._set_cached('cosmic_values', values)
                self._cosmic_values = values
            
            return values
        except Exception as e:
            print(f"Error fetching cosmic values: {e}")
            return {}
        
    async def fetch_items(self) -> List[Dict]:
        cached = self._get_cached('items')
        if cached:
            return cached
        
        await self._fetch_cosmic_values()
        
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
        
        cosmic = await self._fetch_cosmic_values()
        if cosmic:
            values = {name: data['value'] for name, data in cosmic.items()}
            self._set_cached('values', values)
            return values
        
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
        normalized_name = self._normalize_name(name)
        
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
        
        cosmic_data = self._cosmic_values.get(normalized_name, {})
        
        value = cosmic_data.get('value', 0) or float(item.get('value', 0))
        
        thumbnail = cosmic_data.get('icon_url', '')
        if not thumbnail:
            thumbnail = config.get('thumbnail', '')
            if thumbnail and not thumbnail.startswith('http'):
                thumbnail = f'https://biggamesapi.io/image/{thumbnail}'
        
        return {
            'id': pet_id,
            'name': name,
            'normalized_name': normalized_name,
            'rarity': rarity,
            'icon_url': thumbnail,
            'value': value,
            'rap': cosmic_data.get('rap', 0),
            'exist': cosmic_data.get('exist', 0),
            'demand': cosmic_data.get('demand', 5),
            'tradeable': config.get('tradeable', True),
            'game': self.game_name,
            'metadata': {
                'huge': huge,
                'titanic': titanic,
                'golden': config.get('golden', False),
                'rainbow': config.get('rainbow', False),
                'shiny': config.get('shiny', False),
                'variant': cosmic_data.get('variant', 'Normal')
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
