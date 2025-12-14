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
│   ├── owner.py         # Bot owner commands
│   └── item_manage.py   # Manual item management (owner only)
├── api/                 # Game API adapters (legacy, not used)
├── ui/                  # Discord UI components
│   ├── embeds.py        # Message embeds
│   ├── views.py         # Button/select views
│   └── modals.py        # Input modals
├── utils/               # Utility modules
│   ├── database.py      # SQLite database operations
│   ├── cache.py         # Caching system
│   ├── fuzzy.py         # Fuzzy string matching
│   ├── resolver.py      # Item resolution (database-backed)
│   ├── validators.py    # Input validation
│   ├── rate_limit.py    # Rate limiting
│   └── trust_engine.py  # Trust scoring system
├── data/                # Database storage
│   └── trading_bot.db   # SQLite database
└── locales/             # Internationalization
    └── en.json          # English strings
```

### Key Features
1. **Manual Item Management**: Full control over items via Discord commands (no scrapers)
2. **Trade Lifecycle**: draft → pending → accepted → locked → trust_check → in_game_trade → verification → completed
3. **Trust Engine**: Calculates trust scores based on account age, trade history, disputes
4. **Item Resolution**: Database lookup → Alias match → Fuzzy match (Levenshtein ≤ 2)
5. **Anti-Scam**: Detects lowball spam, pressure tactics, bait-and-switch
6. **Immutable Receipts**: SHA-256 hashed trade records

### Item Management Commands (Owner Only)
- `/manage add` - Add a new item with name, value, rarity, and image
- `/manage update` - Update an existing item's details
- `/manage setvalue` - Quickly update an item's value
- `/manage setimage` - Set or update an item's image URL
- `/manage delete` - Remove an item from the database
- `/manage list` - View all items for a game (paginated)
- `/manage bulkvalue` - Update multiple item values at once (JSON format)

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
4. Use `/manage add` commands to populate items

## Tech Stack
- Python 3.11
- discord.py 2.6+
- aiohttp for async HTTP
- aiosqlite for database
- Flask for keep-alive server
- python-Levenshtein for fuzzy matching

## Item Data Model
Items stored in the database have the following fields:
- `game` - Game identifier (ps99, gag, am, bf, sab)
- `item_id` - Unique item identifier
- `name` - Display name
- `value` - Item's worth/value
- `rarity` - Rarity tier (Common, Rare, Legendary, etc.)
- `icon_url` - Image URL for the item
- `tradeable` - Whether the item can be traded

## Trade Features
- Trade offers display item thumbnails (first item image)
- Items show rarity with color-coded emojis
- Values displayed with K/M/B formatting
- Total trade value calculated automatically
- Interactive buttons: Accept, Decline, Counter Offer
- Handoff buttons: "I traded in-game", "Something went wrong", "Upload Proof"

## Recent Changes
- **Dec 2024**: Added trade announcement channel and enhanced buttons
  - New `/settings tradechannel` command for admins to set where trades are announced
  - Trade buttons now include: Accept, Decline, Counter, Negotiate, View Details, View Profile, Message, Share, Bookmark, Report, Help
  - Handoff phase buttons: Complete Trade, Report Issue, Upload Proof, Cancel, Trading Tips
  - Announcement buttons: I'm Interested!, View Items, Trader Profile, Share
  - Added `/settings` command group with: tradechannel, logchannel, modrole, toggle, mintrust, view
  - Trades created without a target are announced to the configured channel
  - All buttons work with trade-specific data embedded in custom_ids
  
- **Dec 2024**: Converted from scraper-based to fully manual item management
  - Removed dependency on external websites for item data
  - Added `/manage` command group for item CRUD operations
  - Items now stored and managed entirely in the database
  - Owner can easily add, update values, and set images for items
