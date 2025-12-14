from typing import List, Dict, Optional, Tuple, Set, Union
from bs4 import BeautifulSoup
import aiohttp
import re
import logging
import asyncio
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)

class WebScraper:
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
    }
    
    @staticmethod
    def parse_value_string(value_str: str) -> float:
        if not value_str:
            return 0.0
        value_str = str(value_str).strip().upper().replace(',', '').replace(' ', '').replace('$', '')
        value_str = re.sub(r'[^\d.KMBT]', '', value_str)
        
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
    def extract_value_from_element(element) -> float:
        if element is None:
            return 0.0
        
        if hasattr(element, 'get'):
            for attr in ['data-value', 'data-price', 'data-worth', 'data-rap', 'value']:
                val = element.get(attr)
                if val:
                    parsed = WebScraper.parse_value_string(val)
                    if parsed > 0:
                        return parsed
        
        if hasattr(element, 'get_text'):
            text = element.get_text(strip=True)
        else:
            text = str(element)
        
        value_patterns = [
            r'(?:Value|Price|RAP|Worth|Cost|Demand)[:\s]*([0-9.,]+\s*[KMBT]?)',
            r'([0-9.,]+\s*[KMBT]?)\s*(?:Value|gems|coins|diamonds|Gems|Coins|Diamonds)',
            r'\$\s*([0-9.,]+\s*[KMBT]?)',
            r'^\s*([0-9.,]+\s*[KMBT]?)\s*$',
            r'([0-9]{1,3}(?:,[0-9]{3})+)',
            r'([0-9]+\.?[0-9]*\s*[KMBT])',
            r'([0-9]+(?:\.[0-9]+)?)',
        ]
        
        for pattern in value_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                parsed = WebScraper.parse_value_string(match.group(1))
                if parsed > 0:
                    return parsed
        
        return 0.0
    
    @staticmethod
    def find_value_in_card(card) -> float:
        value_class_keywords = ['value', 'price', 'worth', 'rap', 'cost', 'gems', 'coins', 'diamond', 'amount', 'number']
        for keyword in value_class_keywords:
            value_elem = card.find(class_=lambda c: c and keyword in c.lower())
            if value_elem:
                val = WebScraper.extract_value_from_element(value_elem)
                if val > 0:
                    return val
        
        for attr in ['data-value', 'data-price', 'data-worth', 'data-rap']:
            val = card.get(attr)
            if val:
                parsed = WebScraper.parse_value_string(val)
                if parsed > 0:
                    return parsed
        
        for tag in ['span', 'div', 'p', 'td', 'strong', 'b', 'em']:
            for elem in card.find_all(tag):
                text = elem.get_text(strip=True)
                if text and re.match(r'^[0-9.,]+\s*[KMBT]?$', text, re.IGNORECASE):
                    val = WebScraper.parse_value_string(text)
                    if val > 0:
                        return val
        
        card_text = card.get_text()
        return WebScraper.extract_value_from_element(card_text)
    
    @staticmethod
    def normalize_name(name: str) -> str:
        return name.lower().replace(' ', '').replace('-', '').replace('_', '').replace("'", '')
    
    @staticmethod
    def extract_image_url(element, base_url: str) -> str:
        if element is None:
            return ''
        
        img_attrs = ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-image', 
                     'data-bg', 'data-background', 'data-srcset', 'srcset', 'data-lazy',
                     'data-img', 'data-url', 'data-thumb', 'data-full', 'data-high-res']
        
        icon_url = ''
        for attr in img_attrs:
            val = element.get(attr, '')
            if val:
                if attr in ['srcset', 'data-srcset']:
                    parts = val.split(',')
                    if parts:
                        first_src = parts[-1].strip().split(' ')[0]
                        if first_src:
                            icon_url = first_src
                            break
                else:
                    icon_url = val
                    break
        
        if not icon_url:
            style = element.get('style', '')
            url_match = re.search(r'url\([\'"]?([^\'")\s]+)[\'"]?\)', style)
            if url_match:
                icon_url = url_match.group(1)
        
        if icon_url and not icon_url.startswith('http'):
            if icon_url.startswith('//'):
                icon_url = 'https:' + icon_url
            elif icon_url.startswith('/'):
                icon_url = base_url.rstrip('/') + icon_url
            elif icon_url.startswith('data:'):
                return ''
            else:
                icon_url = base_url.rstrip('/') + '/' + icon_url
        
        if icon_url and ('placeholder' in icon_url.lower() or 'blank' in icon_url.lower() or 
                         'loading' in icon_url.lower() or '1x1' in icon_url.lower()):
            return ''
        
        return icon_url
    
    @staticmethod
    def find_image_in_card(card, base_url: str) -> str:
        img = card.find('img')
        if img:
            url = WebScraper.extract_image_url(img, base_url)
            if url:
                return url
        
        for tag in card.find_all(['div', 'span', 'a', 'figure']):
            for attr in ['style', 'data-bg', 'data-background', 'data-image']:
                val = tag.get(attr, '')
                if val:
                    url_match = re.search(r'url\([\'"]?([^\'")\s]+)[\'"]?\)', val)
                    if url_match:
                        url = url_match.group(1)
                        if not url.startswith('http'):
                            if url.startswith('//'):
                                url = 'https:' + url
                            elif url.startswith('/'):
                                url = base_url.rstrip('/') + url
                            elif not url.startswith('data:'):
                                url = base_url.rstrip('/') + '/' + url
                        if url and not url.startswith('data:'):
                            return url
        
        for svg in card.find_all('svg'):
            use = svg.find('use')
            if use:
                href = use.get('href', use.get('xlink:href', ''))
                if href:
                    return ''
        
        picture = card.find('picture')
        if picture:
            source = picture.find('source')
            if source:
                srcset = source.get('srcset', '')
                if srcset:
                    parts = srcset.split(',')
                    if parts:
                        url = parts[-1].strip().split(' ')[0]
                        if url and not url.startswith('http'):
                            if url.startswith('//'):
                                url = 'https:' + url
                            elif url.startswith('/'):
                                url = base_url.rstrip('/') + url
                        if url:
                            return url
        
        return ''
    
    @staticmethod
    async def fetch_html(session: aiohttp.ClientSession, url: str) -> Optional[str]:
        try:
            async with session.get(url, headers=WebScraper.HEADERS, timeout=aiohttp.ClientTimeout(total=45)) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.error(f"HTTP {response.status} when fetching {url}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    @staticmethod
    def extract_items_generic(html: str, base_url: str, game_name: str, rarity_list: Optional[List[str]] = None) -> List[Dict]:
        if rarity_list is None:
            rarity_list = ['Mythic', 'Legendary', 'Epic', 'Rare', 'Uncommon', 'Common']
        
        items = []
        soup = BeautifulSoup(html, 'lxml')
        
        card_selectors = [
            'div.pet-card', 'div.item-card', 'div.value-card', 'div.card',
            'div.fruit-card', 'div.brainrot-card', 'div.pet-box',
            'div.pet', 'div.item', 'article.card', 'article.item',
            'div.product', 'div.entry', 'div.result',
            '[class*="-card"]', '[class*="Card"]', '[class*="Item"]',
            '[class*="pet-"]', '[class*="item-"]', '[class*="value-"]',
            '[data-item]', '[data-pet]', '[data-name]', '[data-id]',
            '.grid-item', '.list-item', '.collection-item',
            '.values-item', '.values-card', '.values-row',
            '[class*="row"]', '[class*="entry"]', '[class*="result"]'
        ]
        
        cards = []
        for selector in card_selectors:
            try:
                found = soup.select(selector)
                if found:
                    for f in found:
                        if f not in cards:
                            cards.append(f)
            except:
                continue
        
        if not cards:
            cards = soup.find_all('div', class_=lambda c: c and any(
                x in c.lower() for x in ['card', 'item', 'pet', 'value', 'product', 'entry', 'result', 'row', 'box']
            ))
        
        if not cards:
            all_divs = soup.find_all('div')
            for div in all_divs:
                has_img = div.find('img') is not None
                has_text = bool(div.get_text(strip=True))
                children_count = len(div.find_all(recursive=False))
                if has_img and has_text and 1 <= children_count <= 10:
                    cards.append(div)
        
        seen_names = set()
        
        for card in cards:
            try:
                name = None
                
                for attr in ['data-name', 'data-item', 'data-pet', 'data-title', 'title', 'aria-label']:
                    val = card.get(attr, '').strip()
                    if val and len(val) < 100:
                        name = val
                        break
                
                if not name:
                    name_elem = card.find(class_=lambda c: c and any(
                        x in c.lower() for x in ['name', 'title', 'label', 'heading', 'header']
                    ))
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                
                if not name:
                    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b']:
                        elem = card.find(tag)
                        if elem:
                            text = elem.get_text(strip=True)
                            if text and 2 <= len(text) < 100:
                                name = text
                                break
                
                if not name:
                    img = card.find('img')
                    if img:
                        name = img.get('alt', '').strip() or img.get('title', '').strip()
                
                if not name:
                    for tag in ['span', 'p', 'div', 'a']:
                        elems = card.find_all(tag, recursive=False)
                        for elem in elems:
                            text = elem.get_text(strip=True)
                            if text and 2 <= len(text) < 80 and not any(char.isdigit() for char in text[:3]):
                                if not re.match(r'^[\d.,]+\s*[KMBT]?$', text, re.IGNORECASE):
                                    name = text
                                    break
                        if name:
                            break
                
                if not name:
                    continue
                
                name = re.sub(r'\s+', ' ', name).strip()
                if len(name) < 2 or name.lower() in seen_names:
                    continue
                
                seen_names.add(name.lower())
                
                icon_url = WebScraper.find_image_in_card(card, base_url)
                
                value = WebScraper.find_value_in_card(card)
                
                rarity = 'Common'
                card_html = str(card).lower()
                card_classes = ' '.join(card.get('class', [])).lower()
                
                for r in rarity_list:
                    if r.lower() in card_html or r.lower() in card_classes:
                        rarity = r
                        break
                
                for attr in ['data-rarity', 'data-tier', 'data-type']:
                    attr_val = card.get(attr, '').lower()
                    if attr_val:
                        for r in rarity_list:
                            if r.lower() in attr_val:
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
    def extract_items_table(html: str, base_url: str, game_name: str, rarity_list: Optional[List[str]] = None) -> List[Dict]:
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
                    if len(cells) < 1:
                        continue
                    
                    name = None
                    icon_url = ''
                    value = 0.0
                    
                    for attr in ['data-name', 'data-item', 'data-pet', 'title']:
                        val = row.get(attr, '')
                        if val and isinstance(val, str) and len(val) < 100:
                            name = val.strip()
                            break
                    
                    for cell in cells:
                        if not icon_url:
                            icon_url = WebScraper.find_image_in_card(cell, base_url)
                        
                        if not name:
                            img = cell.find('img')
                            if img:
                                alt_val = img.get('alt', '')
                                title_val = img.get('title', '')
                                name = (alt_val.strip() if isinstance(alt_val, str) else '') or (title_val.strip() if isinstance(title_val, str) else '')
                        
                        if not name:
                            cell_text = cell.get_text(strip=True)
                            if cell_text and 2 <= len(cell_text) < 100:
                                if not re.match(r'^[\d.,]+\s*[KMBT]?$', cell_text, re.IGNORECASE):
                                    if not any(char.isdigit() for char in cell_text[:3]):
                                        name = cell_text
                        
                        if value == 0:
                            value = WebScraper.extract_value_from_element(cell)
                    
                    if not name or name.lower() in seen_names:
                        continue
                    
                    name = re.sub(r'\s+', ' ', name).strip()
                    seen_names.add(name.lower())
                    
                    rarity = 'Common'
                    row_html = str(row).lower()
                    for r in rarity_list:
                        if r.lower() in row_html:
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
    def extract_items_list(html: str, base_url: str, game_name: str, rarity_list: Optional[List[str]] = None) -> List[Dict]:
        if rarity_list is None:
            rarity_list = ['Mythic', 'Legendary', 'Epic', 'Rare', 'Uncommon', 'Common']
        
        items = []
        soup = BeautifulSoup(html, 'lxml')
        
        list_items = soup.find_all('li')
        seen_names = set()
        
        for li in list_items:
            try:
                name = None
                value = 0.0
                
                for attr in ['data-name', 'data-item', 'data-pet', 'title']:
                    val = li.get(attr, '')
                    if val and isinstance(val, str) and len(val) < 100:
                        name = val.strip()
                        break
                
                icon_url = WebScraper.find_image_in_card(li, base_url)
                
                if not name:
                    img = li.find('img')
                    if img:
                        alt_val = img.get('alt', '')
                        title_val = img.get('title', '')
                        name = (alt_val.strip() if isinstance(alt_val, str) else '') or (title_val.strip() if isinstance(title_val, str) else '')
                
                if not name:
                    for tag in ['h3', 'h4', 'h5', 'strong', 'b', 'span', 'a']:
                        elem = li.find(tag)
                        if elem:
                            text = elem.get_text(strip=True)
                            if text and 2 <= len(text) < 80:
                                if not re.match(r'^[\d.,]+\s*[KMBT]?$', text, re.IGNORECASE):
                                    name = text
                                    break
                
                if not name:
                    text_content = li.get_text(strip=True)
                    parts = re.split(r'[-:|]', text_content)
                    if parts:
                        candidate = parts[0].strip()
                        if 2 <= len(candidate) < 80:
                            if not re.match(r'^[\d.,]+\s*[KMBT]?$', candidate, re.IGNORECASE):
                                name = candidate
                
                if not name or name.lower() in seen_names:
                    continue
                
                name = re.sub(r'\s+', ' ', name).strip()
                seen_names.add(name.lower())
                
                value = WebScraper.find_value_in_card(li)
                
                rarity = 'Common'
                li_html = str(li).lower()
                for r in rarity_list:
                    if r.lower() in li_html:
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
                                  rarity_list: Optional[List[str]] = None) -> Tuple[List[Dict], List[str]]:
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
                          rarity_list: Optional[List[str]] = None, base_url: Optional[str] = None,
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
