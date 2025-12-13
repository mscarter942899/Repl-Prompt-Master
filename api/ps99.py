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
        self._items_data: List[Dict] = []
        
    def _parse_value_string(self, value_str: str) -> float:
        if not value_str:
            return 0.0
        value_str = str(value_str).strip().upper().replace(',', '').replace(' ', '')
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
    
    async def _fetch_from_values_site(self) -> List[Dict]:
        cached = self._get_cached('items_from_site')
        if cached:
            return cached
        
        items = []
        try:
            session = await self.get_session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            async with session.get(self.values_url, headers=headers) as response:
                if response.status != 200:
                    print(f"PS99 values site returned status {response.status}")
                    return []
                html = await response.text()
            
            pet_pattern = re.compile(
                r'<div[^>]*class="[^"]*pet-card[^"]*"[^>]*>.*?'
                r'<img[^>]*src="([^"]*)"[^>]*>.*?'
                r'<[^>]*>([^<]+)</[^>]*>.*?'
                r'(?:Value|RAP)[:\s]*([0-9.,]+[KMBT]?).*?'
                r'(?:Demand[:\s]*(\d+))?',
                re.DOTALL | re.IGNORECASE
            )
            
            img_pattern = re.compile(r'<img[^>]*src="([^"]+)"[^>]*>', re.IGNORECASE)
            name_pattern = re.compile(r'<(?:h[1-6]|span|div|p)[^>]*class="[^"]*(?:pet-name|name|title)[^"]*"[^>]*>([^<]+)<', re.IGNORECASE)
            value_pattern = re.compile(r'(?:Value|RAP)[:\s]*([0-9.,]+\s*[KMBT]?)', re.IGNORECASE)
            
            blocks = re.split(r'<div[^>]*class="[^"]*(?:pet-card|item-card|pet-box|card)[^"]*"', html)
            
            for block in blocks[1:]:
                try:
                    img_match = img_pattern.search(block)
                    icon_url = ''
                    if img_match:
                        icon_url = img_match.group(1)
                        if icon_url and not icon_url.startswith('http'):
                            icon_url = f'https://petsimulatorvalues.com{icon_url}'
                    
                    name = ''
                    name_match = name_pattern.search(block)
                    if name_match:
                        name = name_match.group(1).strip()
                    else:
                        alt_match = re.search(r'alt="([^"]+)"', block)
                        if alt_match:
                            name = alt_match.group(1).strip()
                    
                    if not name:
                        continue
                    
                    value = 0.0
                    value_match = value_pattern.search(block)
                    if value_match:
                        value = self._parse_value_string(value_match.group(1))
                    
                    demand = 5
                    demand_match = re.search(r'Demand[:\s]*(\d+)', block, re.IGNORECASE)
                    if demand_match:
                        demand = int(demand_match.group(1))
                    
                    rarity = 'Common'
                    if 'titanic' in name.lower() or 'titanic' in block.lower():
                        rarity = 'Titanic'
                    elif 'huge' in name.lower() or 'huge' in block.lower():
                        rarity = 'Huge'
                    elif 'legendary' in block.lower():
                        rarity = 'Legendary'
                    elif 'epic' in block.lower():
                        rarity = 'Epic'
                    elif 'rare' in block.lower():
                        rarity = 'Rare'
                    
                    items.append({
                        'id': self._normalize_name(name),
                        'name': name,
                        'normalized_name': self._normalize_name(name),
                        'rarity': rarity,
                        'icon_url': icon_url,
                        'value': value,
                        'demand': demand,
                        'tradeable': True,
                        'game': self.game_name,
                        'metadata': {
                            'huge': 'huge' in name.lower(),
                            'titanic': 'titanic' in name.lower()
                        }
                    })
                except Exception as e:
                    continue
            
            if items:
                self._set_cached('items_from_site', items)
                self._items_data = items
                print(f"PS99: Fetched {len(items)} items from values site")
            
            return items
        except Exception as e:
            print(f"Error fetching PS99 values: {e}")
            return []
    
    async def _fetch_from_biggames_api(self) -> List[Dict]:
        try:
            data = await self._request(f'{self.base_url}/collection/Pets')
            if data and 'data' in data:
                items = []
                for item in data['data']:
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
                    
                    items.append({
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
                    })
                return items
        except Exception as e:
            print(f"Error fetching from BigGames API: {e}")
        return []
        
    async def fetch_items(self) -> List[Dict]:
        cached = self._get_cached('items')
        if cached:
            return cached
        
        items = await self._fetch_from_values_site()
        
        if not items:
            items = await self._fetch_from_biggames_api()
        
        if not items:
            items = self._load_fallback()
        
        if items:
            self._set_cached('items', items)
        
        return items
    
    async def fetch_item(self, item_id: str) -> Optional[Dict]:
        items = await self.fetch_items()
        norm_id = self._normalize_name(item_id)
        for item in items:
            if item['id'] == item_id or item['normalized_name'] == norm_id:
                return item
        return None
    
    async def fetch_values(self) -> Dict[str, float]:
        items = await self.fetch_items()
        return {item['id']: item['value'] for item in items}
    
    async def fetch_icons(self) -> Dict[str, str]:
        items = await self.fetch_items()
        return {item['id']: item['icon_url'] for item in items if item.get('icon_url')}
    
    async def health_check(self) -> bool:
        try:
            items = await self.fetch_items()
            return len(items) > 0
        except:
            return False
    
    def normalize_item(self, item: Dict) -> Dict:
        return item
    
    def _load_fallback(self) -> List[Dict]:
        if os.path.exists(self.fallback_path):
            try:
                with open(self.fallback_path, 'r') as f:
                    data = json.load(f)
                    items = []
                    for item in data.get('items', []):
                        items.append({
                            'id': item.get('id', self._normalize_name(item.get('name', ''))),
                            'name': item.get('name', 'Unknown'),
                            'normalized_name': self._normalize_name(item.get('name', '')),
                            'rarity': item.get('rarity', 'Common'),
                            'icon_url': item.get('icon', ''),
                            'value': float(item.get('value', 0)),
                            'tradeable': item.get('tradeable', True),
                            'game': self.game_name,
                            'metadata': {
                                'huge': item.get('huge', False),
                                'titanic': item.get('titanic', False)
                            }
                        })
                    return items
            except Exception as e:
                print(f"Error loading PS99 fallback: {e}")
        return []

def setup():
    APIRegistry.register('ps99', PS99Adapter())
