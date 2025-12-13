from typing import List, Dict, Optional, Tuple, Set
from bs4 import BeautifulSoup
import aiohttp
import re
import logging
import asyncio
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, urlunparse

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
    def detect_pagination_links(html: str, current_url: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, 'lxml')
        pagination_urls = set()
        parsed_current = urlparse(current_url)
        
        pagination_selectors = [
            'ul.pagination a', 'nav.pagination a', 'div.pagination a',
            '.pager a', '.page-numbers', '.paginate a', '[class*="pagination"] a',
            'a.page-link', 'a.page-number', '.pages a', '.page-nav a',
            'a[href*="page="]', 'a[href*="p="]', 'a[href*="/page/"]',
            '.next a', '.prev a', 'a.next', 'a.prev',
            '[rel="next"]', '[rel="prev"]'
        ]
        
        for selector in pagination_selectors:
            try:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    if not href or href == '#' or 'javascript:' in href:
                        continue
                    
                    full_url = urljoin(current_url, href)
                    parsed_link = urlparse(full_url)
                    
                    if parsed_link.netloc == parsed_current.netloc:
                        pagination_urls.add(full_url)
            except Exception:
                continue
        
        page_param_patterns = [
            (r'page[=](\d+)', 'page'),
            (r'p[=](\d+)', 'p'),
            (r'/page/(\d+)', None),
        ]
        
        for pattern, param in page_param_patterns:
            matches = re.findall(pattern, current_url, re.IGNORECASE)
            if matches:
                current_page = int(matches[0])
                for offset in range(-2, 10):
                    new_page = current_page + offset
                    if new_page < 1:
                        continue
                    
                    if param:
                        parsed = urlparse(current_url)
                        query = parse_qs(parsed.query)
                        query[param] = [str(new_page)]
                        new_query = urlencode(query, doseq=True)
                        new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, 
                                            parsed.params, new_query, parsed.fragment))
                    else:
                        new_url = re.sub(r'/page/\d+', f'/page/{new_page}', current_url)
                    
                    pagination_urls.add(new_url)
        
        return list(pagination_urls)
    
    @staticmethod
    async def scrape_single_page(session: aiohttp.ClientSession, url: str, 
                                  game_name: str, base_url: str, 
                                  rarity_list: List[str] = None) -> Tuple[List[Dict], List[str]]:
        html = await WebScraper.fetch_html(session, url)
        if not html:
            return [], []
        
        items = WebScraper.extract_items_generic(html, base_url, game_name, rarity_list)
        
        if not items:
            items = WebScraper.extract_items_table(html, base_url, game_name, rarity_list)
        
        if not items:
            items = WebScraper.extract_items_list(html, base_url, game_name, rarity_list)
        
        pagination_links = WebScraper.detect_pagination_links(html, url, base_url)
        
        return items, pagination_links
    
    @staticmethod
    async def scrape_items(session: aiohttp.ClientSession, url: str, game_name: str, 
                          rarity_list: List[str] = None, base_url: str = None,
                          max_pages: int = 10) -> List[Dict]:
        if base_url is None:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        all_items = []
        visited_urls: Set[str] = set()
        urls_to_visit = [url]
        pages_scraped = 0
        failed_pages = 0
        
        logger.info(f"{game_name}: Starting scrape from {url}")
        
        while urls_to_visit and pages_scraped < max_pages:
            current_url = urls_to_visit.pop(0)
            
            normalized_url = current_url.rstrip('/').lower()
            if normalized_url in visited_urls:
                continue
            
            visited_urls.add(normalized_url)
            
            items, pagination_links = await WebScraper.scrape_single_page(
                session, current_url, game_name, base_url, rarity_list
            )
            
            if items:
                pages_scraped += 1
                items_added = 0
                for item in items:
                    if not any(existing['id'] == item['id'] for existing in all_items):
                        all_items.append(item)
                        items_added += 1
                logger.debug(f"{game_name}: Page {pages_scraped} - {items_added} new items from {current_url}")
            else:
                failed_pages += 1
                logger.debug(f"{game_name}: No items found on {current_url}")
            
            for link in pagination_links:
                normalized_link = link.rstrip('/').lower()
                if normalized_link not in visited_urls and link not in urls_to_visit:
                    urls_to_visit.append(link)
            
            if urls_to_visit and pages_scraped < max_pages:
                await asyncio.sleep(0.5)
        
        if urls_to_visit and pages_scraped >= max_pages:
            logger.info(f"{game_name}: Stopped at max_pages limit ({max_pages}), {len(urls_to_visit)} pages remaining")
        
        logger.info(f"{game_name}: Scraped {len(all_items)} items from {pages_scraped} pages ({failed_pages} failed)")
        return all_items
