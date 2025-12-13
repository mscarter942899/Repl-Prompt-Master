from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
import aiohttp
import re
import logging

logger = logging.getLogger(__name__)

class WebScraper:
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    @staticmethod
    def parse_value_string(value_str: str) -> float:
        if not value_str:
            return 0.0
        value_str = str(value_str).strip().upper().replace(',', '').replace(' ', '').replace('$', '')
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
    
    @staticmethod
    def normalize_name(name: str) -> str:
        return name.lower().replace(' ', '').replace('-', '').replace('_', '').replace("'", '')
    
    @staticmethod
    async def fetch_html(session: aiohttp.ClientSession, url: str) -> Optional[str]:
        try:
            async with session.get(url, headers=WebScraper.HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.error(f"HTTP {response.status} when fetching {url}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    @staticmethod
    def extract_items_generic(html: str, base_url: str, game_name: str, rarity_list: List[str] = None) -> List[Dict]:
        if rarity_list is None:
            rarity_list = ['Mythic', 'Legendary', 'Epic', 'Rare', 'Uncommon', 'Common']
        
        items = []
        soup = BeautifulSoup(html, 'lxml')
        
        card_selectors = [
            'div.pet-card', 'div.item-card', 'div.value-card', 'div.card',
            'div.fruit-card', 'div.brainrot-card', 'div.pet-box',
            '[class*="card"]', '[class*="item"]', '[class*="pet"]'
        ]
        
        cards = []
        for selector in card_selectors:
            found = soup.select(selector)
            if found:
                cards.extend(found)
                break
        
        if not cards:
            cards = soup.find_all('div', class_=lambda c: c and any(x in c.lower() for x in ['card', 'item', 'pet', 'value']))
        
        seen_names = set()
        
        for card in cards:
            try:
                name = None
                img = card.find('img')
                if img:
                    name = img.get('alt', '').strip()
                
                if not name:
                    name_elem = card.find(class_=lambda c: c and any(x in c.lower() for x in ['name', 'title']))
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                
                if not name:
                    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'p', 'div']:
                        elem = card.find(tag)
                        if elem:
                            text = elem.get_text(strip=True)
                            if text and len(text) < 100 and not any(char.isdigit() for char in text[:3]):
                                name = text
                                break
                
                if not name or name.lower() in seen_names:
                    continue
                
                seen_names.add(name.lower())
                
                icon_url = ''
                if img:
                    icon_url = img.get('src', '') or img.get('data-src', '')
                    if icon_url and not icon_url.startswith('http'):
                        if icon_url.startswith('//'):
                            icon_url = 'https:' + icon_url
                        elif icon_url.startswith('/'):
                            icon_url = base_url.rstrip('/') + icon_url
                        else:
                            icon_url = base_url.rstrip('/') + '/' + icon_url
                
                value = 0.0
                card_text = card.get_text()
                value_patterns = [
                    r'(?:Value|Price|RAP|Worth|Cost)[:\s]*([0-9.,]+\s*[KMBT]?)',
                    r'([0-9.,]+\s*[KMBT]?)\s*(?:Value|gems|coins|diamonds)',
                    r'\$\s*([0-9.,]+\s*[KMBT]?)',
                ]
                for pattern in value_patterns:
                    match = re.search(pattern, card_text, re.IGNORECASE)
                    if match:
                        value = WebScraper.parse_value_string(match.group(1))
                        if value > 0:
                            break
                
                rarity = 'Common'
                card_lower = str(card).lower()
                for r in rarity_list:
                    if r.lower() in card_lower:
                        rarity = r
                        break
                
                items.append({
                    'id': WebScraper.normalize_name(name),
                    'name': name,
                    'normalized_name': WebScraper.normalize_name(name),
                    'rarity': rarity,
                    'icon_url': icon_url,
                    'value': value,
                    'tradeable': True,
                    'game': game_name,
                    'metadata': {}
                })
            except Exception as e:
                continue
        
        return items
    
    @staticmethod
    def extract_items_table(html: str, base_url: str, game_name: str, rarity_list: List[str] = None) -> List[Dict]:
        if rarity_list is None:
            rarity_list = ['Mythic', 'Legendary', 'Epic', 'Rare', 'Uncommon', 'Common']
        
        items = []
        soup = BeautifulSoup(html, 'lxml')
        
        tables = soup.find_all('table')
        seen_names = set()
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:
                try:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 2:
                        continue
                    
                    name = None
                    icon_url = ''
                    value = 0.0
                    
                    for cell in cells:
                        img = cell.find('img')
                        if img:
                            if not name:
                                name = img.get('alt', '').strip()
                            if not icon_url:
                                icon_url = img.get('src', '') or img.get('data-src', '')
                        
                        cell_text = cell.get_text(strip=True)
                        if not name and cell_text and len(cell_text) < 100:
                            if not any(char.isdigit() for char in cell_text[:3]):
                                name = cell_text
                        
                        if value == 0:
                            value_match = re.search(r'([0-9.,]+\s*[KMBT]?)', cell_text)
                            if value_match:
                                parsed = WebScraper.parse_value_string(value_match.group(1))
                                if parsed > 0:
                                    value = parsed
                    
                    if not name or name.lower() in seen_names:
                        continue
                    
                    seen_names.add(name.lower())
                    
                    if icon_url and not icon_url.startswith('http'):
                        if icon_url.startswith('//'):
                            icon_url = 'https:' + icon_url
                        elif icon_url.startswith('/'):
                            icon_url = base_url.rstrip('/') + icon_url
                        else:
                            icon_url = base_url.rstrip('/') + '/' + icon_url
                    
                    rarity = 'Common'
                    row_lower = str(row).lower()
                    for r in rarity_list:
                        if r.lower() in row_lower:
                            rarity = r
                            break
                    
                    items.append({
                        'id': WebScraper.normalize_name(name),
                        'name': name,
                        'normalized_name': WebScraper.normalize_name(name),
                        'rarity': rarity,
                        'icon_url': icon_url,
                        'value': value,
                        'tradeable': True,
                        'game': game_name,
                        'metadata': {}
                    })
                except:
                    continue
        
        return items
    
    @staticmethod
    def extract_items_list(html: str, base_url: str, game_name: str, rarity_list: List[str] = None) -> List[Dict]:
        if rarity_list is None:
            rarity_list = ['Mythic', 'Legendary', 'Epic', 'Rare', 'Uncommon', 'Common']
        
        items = []
        soup = BeautifulSoup(html, 'lxml')
        
        list_items = soup.find_all('li')
        seen_names = set()
        
        for li in list_items:
            try:
                name = None
                icon_url = ''
                value = 0.0
                
                img = li.find('img')
                if img:
                    name = img.get('alt', '').strip()
                    icon_url = img.get('src', '') or img.get('data-src', '')
                
                if not name:
                    text_content = li.get_text(strip=True)
                    parts = re.split(r'[-:|]', text_content)
                    if parts:
                        name = parts[0].strip()
                        if len(name) > 100:
                            continue
                
                if not name or name.lower() in seen_names:
                    continue
                
                seen_names.add(name.lower())
                
                li_text = li.get_text()
                value_match = re.search(r'([0-9.,]+\s*[KMBT]?)', li_text)
                if value_match:
                    value = WebScraper.parse_value_string(value_match.group(1))
                
                if icon_url and not icon_url.startswith('http'):
                    if icon_url.startswith('//'):
                        icon_url = 'https:' + icon_url
                    elif icon_url.startswith('/'):
                        icon_url = base_url.rstrip('/') + icon_url
                    else:
                        icon_url = base_url.rstrip('/') + '/' + icon_url
                
                rarity = 'Common'
                li_lower = str(li).lower()
                for r in rarity_list:
                    if r.lower() in li_lower:
                        rarity = r
                        break
                
                items.append({
                    'id': WebScraper.normalize_name(name),
                    'name': name,
                    'normalized_name': WebScraper.normalize_name(name),
                    'rarity': rarity,
                    'icon_url': icon_url,
                    'value': value,
                    'tradeable': True,
                    'game': game_name,
                    'metadata': {}
                })
            except:
                continue
        
        return items
    
    @staticmethod
    async def scrape_items(session: aiohttp.ClientSession, url: str, game_name: str, 
                          rarity_list: List[str] = None, base_url: str = None) -> List[Dict]:
        html = await WebScraper.fetch_html(session, url)
        if not html:
            return []
        
        if base_url is None:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        items = WebScraper.extract_items_generic(html, base_url, game_name, rarity_list)
        
        if not items:
            items = WebScraper.extract_items_table(html, base_url, game_name, rarity_list)
        
        if not items:
            items = WebScraper.extract_items_list(html, base_url, game_name, rarity_list)
        
        logger.info(f"{game_name}: Scraped {len(items)} items from {url}")
        return items
