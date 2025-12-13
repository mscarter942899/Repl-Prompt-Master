from typing import List, Dict, Optional
import json
import os
import re
from .base import GameAPIAdapter, APIRegistry
from utils.scraper import WebScraper

class AdoptMeAdapter(GameAPIAdapter):
    def __init__(self):
        super().__init__('am')
        self.default_values_url = 'https://adoptmetradingvalues.com/pet-value-list.php'
        self.values_url = self.default_values_url
        self.fallback_path = 'data/fallback_am.json'
        self.rarity_list = ['Legendary', 'Ultra Rare', 'Rare', 'Uncommon', 'Common']
        
    async def _get_current_url(self) -> str:
        try:
            from utils.database import get_game_source
            custom_url = await get_game_source(self.game_name)
            if custom_url:
                return custom_url
        except:
            pass
        return self.values_url or self.default_values_url
        
    async def fetch_items(self) -> List[Dict]:
        cached = self._get_cached('items')
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
                item['metadata'] = {
                    'neon': 'neon' in name_lower,
                    'mega_neon': 'mega' in name_lower
                }
            
            if items:
                print(f"AM: Fetched {len(items)} items from {url}")
        except Exception as e:
            print(f"Error fetching AM values: {e}")
        
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
                                'neon': item.get('neon', False),
                                'mega_neon': item.get('mega_neon', False)
                            }
                        })
                    return items
            except:
                pass
        return []

def setup():
    APIRegistry.register('am', AdoptMeAdapter())
