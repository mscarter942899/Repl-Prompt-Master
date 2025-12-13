from typing import List, Dict, Optional
import json
import os
import re
from .base import GameAPIAdapter, APIRegistry

class AdoptMeAdapter(GameAPIAdapter):
    def __init__(self):
        super().__init__('am')
        self.values_url = 'https://adoptmetradingvalues.com/pet-value-list.php'
        self.fallback_path = 'data/fallback_am.json'
        
    def _parse_value_string(self, value_str: str) -> float:
        if not value_str:
            return 0.0
        value_str = str(value_str).strip().replace(',', '').replace(' ', '')
        try:
            return float(value_str) * 1_000_000
        except:
            return 0.0
        
    async def fetch_items(self) -> List[Dict]:
        cached = self._get_cached('items')
        if cached:
            return cached
        
        items = []
        try:
            session = await self.get_session()
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            async with session.get(self.values_url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    blocks = re.split(r'<div[^>]*class="[^"]*(?:pet-card|item-card|pet-box)[^"]*"', html)
                    
                    for block in blocks[1:]:
                        try:
                            img_match = re.search(r'<img[^>]*src="([^"]+)"', block)
                            icon_url = img_match.group(1) if img_match else ''
                            if icon_url and not icon_url.startswith('http'):
                                icon_url = f'https://adoptmetradingvalues.com{icon_url}'
                            
                            name_match = re.search(r'(?:alt="([^"]+)"|<[^>]*class="[^"]*pet-name[^"]*"[^>]*>([^<]+)<)', block)
                            name = ''
                            if name_match:
                                name = (name_match.group(1) or name_match.group(2) or '').strip()
                            
                            if not name:
                                continue
                            
                            value_match = re.search(r'(?:Value|Score)[:\s]*([0-9.,]+)', block, re.IGNORECASE)
                            value = self._parse_value_string(value_match.group(1)) if value_match else 0
                            
                            rarity = 'Common'
                            for r in ['Legendary', 'Ultra Rare', 'Rare', 'Uncommon']:
                                if r.lower() in block.lower():
                                    rarity = r
                                    break
                            
                            items.append({
                                'id': self._normalize_name(name),
                                'name': name,
                                'normalized_name': self._normalize_name(name),
                                'rarity': rarity,
                                'icon_url': icon_url,
                                'value': value,
                                'tradeable': True,
                                'game': self.game_name,
                                'metadata': {
                                    'neon': 'neon' in name.lower(),
                                    'mega_neon': 'mega' in name.lower()
                                }
                            })
                        except:
                            continue
                    
                    if items:
                        print(f"AM: Fetched {len(items)} items from values site")
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
