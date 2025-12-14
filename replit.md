# Roblox Trading Discord Bot

## Overview
A production-grade Discord bot for secure Roblox trading coordination across multiple games:
- Pet Simulator 99 (PS99)
- Grow a Garden (GAG)
- Adopt Me (AM)
- Blox Fruits (BF)
- Steal a Brainrot (SAB)

## Architecture

### Project Structure
```
/
├── main.py              # Bot entry point
├── keep_alive.py        # Flask server for uptime
├── cogs/                # Discord command modules
│   ├── trading.py       # Trade lifecycle management
│   ├── inventory.py     # User inventory management
│   ├── profile.py       # User profiles & Roblox linking
│   ├── search.py        # Item search & lookup
│   ├── auctions.py      # Auction system
│   ├── moderation.py    # Mod tools
│   ├── analytics.py     # Statistics
│   └── owner.py         # Bot owner commands
├── api/                 # Game API adapters
│   ├── base.py          # Abstract adapter interface
│   ├── ps99.py          # Pet Simulator 99 API
│   ├── gag.py           # Grow a Garden API
│   ├── am.py            # Adopt Me API
│   ├── bf.py            # Blox Fruits API
│   └── sab.py           # Steal a Brainrot API
├── ui/                  # Discord UI components
│   ├── embeds.py        # Message embeds
│   ├── views.py         # Button/select views
│   └── modals.py        # Input modals
├── utils/               # Utility modules
│   ├── database.py      # SQLite database operations
│   ├── cache.py         # Caching system
│   ├── fuzzy.py         # Fuzzy string matching
│   ├── resolver.py      # Item resolution pipeline
│   ├── validators.py    # Input validation
│   ├── rate_limit.py    # Rate limiting
│   └── trust_engine.py  # Trust scoring system
├── data/                # Fallback item data
│   └── fallback_*.json  # Per-game fallback data
└── locales/             # Internationalization
    └── en.json          # English strings
```

### Key Features
1. **Trade Lifecycle**: draft → pending → accepted → locked → trust_check → in_game_trade → verification → completed
2. **Trust Engine**: Calculates trust scores based on account age, trade history, disputes
3. **Item Resolution**: API lookup → Alias match → Fuzzy match (Levenshtein ≤ 2)
4. **Anti-Scam**: Detects lowball spam, pressure tactics, bait-and-switch
5. **Immutable Receipts**: SHA-256 hashed trade records

### Slash Commands
- `/trade create` - Create a trade offer
- `/trade view` - View trade details
- `/trade history` - View trade history
- `/trade cancel` - Cancel a pending trade
- `/trade verify` - Verify trade receipt by hash
- `/auction create` - Create a new auction
- `/auction bid` - Place a bid on an auction
- `/auction list` - List active auctions
- `/auction view` - View auction details
- `/auction cancel` - Cancel your auction
- `/inventory view` - View inventory
- `/inventory add` - Add item to inventory
- `/profile` - View trading profile
- `/link_roblox` - Link Roblox account
- `/search` - Search for items
- `/item` - Get item details
- `/values` - View top valued items

### Moderation Commands
- `/mod audit_trade` - View detailed trade audit log
- `/mod force_resolve` - Force resolve a disputed trade
- `/mod ban_user` - Ban a user from trading
- `/mod unban_user` - Unban a user
- `/mod rollback_rep` - Reset user reputation
- `/mod flag_user` - Flag a user for review
- `/mod replay_trade` - View visual timeline of a trade

## Setup Required
1. Set `DISCORD_TOKEN` in Secrets
2. Bot will auto-initialize database on startup
3. Commands sync automatically

## Tech Stack
- Python 3.11
- discord.py 2.6+
- aiohttp for async HTTP
- aiosqlite for database
- Flask for keep-alive server
- python-Levenshtein for fuzzy matching
- BeautifulSoup/lxml for web scraping

## Web Scraper Features
The scraper (`utils/scraper.py`) is designed to work with various website layouts:
- **Multi-page support**: Automatically follows pagination links (up to 10 pages by default)
- **Flexible value extraction**: Detects values from data attributes, class-based elements, and text patterns
- **Multiple layout support**: Handles card layouts, tables, and list-based sites
- **Value formats**: Recognizes values with K/M/B/T multipliers, commas, labels (Value:, Price:, etc.)
- **Rate limiting**: 0.5 second delay between page requests to avoid overwhelming sites
- **Enhanced image extraction**: Supports lazy-loaded images (data-src, data-lazy-src, data-original), srcset, picture elements, and CSS background images
- **Comprehensive selectors**: Uses 20+ CSS selectors to find item cards including data attributes, class patterns, and structural detection
- **Smart name extraction**: Prioritizes data attributes, heading tags, image alt text, and structured text

## Trade Features
- Trade offers display item thumbnails (first item image)
- Items show rarity with color-coded emojis
- Values displayed with K/M/B formatting
- Total trade value calculated automatically
- Interactive buttons: Accept, Decline, Counter Offer
- Handoff buttons: "I traded in-game", "Something went wrong", "Upload Proof"
