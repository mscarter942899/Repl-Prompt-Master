from typing import List, Dict, Optional
import json
import os
import re
from .base import GameAPIAdapter, APIRegistry
from utils.scraper import WebScraper

class PS99Adapter(GameAPIAdapter):
    def __init__(self):
        super().__init__('ps99')
        self.base_url = 'https://biggamesapi.io/api'
        self.rap_url = 'https://biggamesapi.io/api/rap'
        self.default_values_url = 'https://petsimulatorvalues.com/values.php?category=all'
        self.values_url = self.default_values_url
        self.fallback_path = 'data/fallback_ps99.json'
        self._items_data: List[Dict] = []
        self._rap_data: Dict[str, float] = {}
        self.rarity_list = ['Titanic', 'Huge', 'Legendary', 'Epic', 'Rare', 'Uncommon', 'Common']
        
    async def _get_current_url(self) -> str:
        try:
            from utils.database import get_game_source
            custom_url = await get_game_source(self.game_name)
            if custom_url:
                return custom_url
        except:
            pass
        return self.values_url or self.default_values_url
    
    async def _fetch_rap_data(self) -> Dict[str, float]:
        cached = self._get_cached('rap_data')
        if cached:
            return cached
        
        rap_dict = {}
        try:
            data = await self._request(self.rap_url)
            if data and 'data' in data:
                for item in data['data']:
                    config = item.get('configData', {})
                    pet_id = config.get('id', str(item.get('_id', '')))
                    rap_value = item.get('value', 0)
                    if pet_id and rap_value:
                        rap_dict[pet_id.lower()] = float(rap_value)
                        variants = []
                        if config.get('pt'):
                            variants.append(('pt', config.get('pt')))
                        if config.get('sh'):
                            variants.append(('sh', config.get('sh')))
                        key_base = pet_id.lower()
                        for var_type, var_val in variants:
                            if var_val:
                                variant_key = f"{key_base}_{var_type}"
                                rap_dict[variant_key] = float(rap_value)
                
                self._set_cached('rap_data', rap_dict)
                self._rap_data = rap_dict
                print(f"PS99: Fetched RAP data for {len(rap_dict)} items")
        except Exception as e:
            print(f"Error fetching PS99 RAP data: {e}")
        
        return rap_dict
    
    async def _fetch_from_values_site(self) -> List[Dict]:
        cached = self._get_cached('items_from_site')
        if cached:
            return cached
        
        items = []
        try:
            session = await self.get_session()
            url = await self._get_current_url()
            items = await WebScraper.scrape_items(
                session, url, self.game_name,
                rarity_list=self.rarity_list
            )
            
            for item in items:
                name_lower = item['name'].lower()
                if 'titanic' in name_lower:
                    item['rarity'] = 'Titanic'
                    item['metadata'] = {'titanic': True, 'huge': False}
                elif 'huge' in name_lower:
                    item['rarity'] = 'Huge'
                    item['metadata'] = {'titanic': False, 'huge': True}
                else:
                    item['metadata'] = {'titanic': False, 'huge': False}
            
            if items:
                self._set_cached('items_from_site', items)
                self._items_data = items
                print(f"PS99: Fetched {len(items)} items from {url}")
            
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
        
        rap_data = await self._fetch_rap_data()
        
        items = await self._fetch_from_biggames_api()
        
        if not items:
            items = await self._fetch_from_values_site()
        
        if not items:
            items = self._load_fallback()
        
        if items and rap_data:
            for item in items:
                item_id = item.get('id', '').lower()
                item_name = self._normalize_name(item.get('name', ''))
                
                rap_value = rap_data.get(item_id) or rap_data.get(item_name, 0)
                
                if 'metadata' not in item:
                    item['metadata'] = {}
                item['metadata']['rap'] = rap_value
                
                if not item.get('value') and rap_value:
                    item['value'] = rap_value
        
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
