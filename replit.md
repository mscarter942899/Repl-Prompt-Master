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
- `/manage add` - Add a new item with name, value, rarity, and image (supports file uploads!)
- `/manage update` - Update an existing item's details (supports file uploads!)
- `/manage setvalue` - Quickly update an item's value
- `/manage setimage` - Set or update an item's image (supports file uploads!)
- `/manage delete` - Remove an item from the database
- `/manage list` - View all items for a game (paginated)
- `/manage bulkvalue` - Update multiple item values at once (JSON format)

### Image Upload Support
You can upload images directly from your device when managing items:
- Supported formats: PNG, JPEG, GIF, WebP
- Maximum file size: 8MB
- Simply attach an image when using `/manage add`, `/manage update`, or `/manage setimage`
- You can also still use image URLs if preferred

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
- **Dec 2024**: Enhanced UI with Custom Diamond Emoji & Improved Buttons
  - Added custom diamond emoji <:diamonds:1449866490495893577> for all gem displays
  - Created ui/constants.py for centralized emoji and formatting constants
  - Enhanced announcement view with 5 buttons: I'm Interested!, View Items, Trader Profile, Share, Save
  - Improved Trader Profile button with trust progress bars and detailed stats
  - Enhanced View Items button with detailed item breakdown and values
  - Added bookmark/save functionality for trades
  - Better trade announcement embeds with game emojis and total value display
  - Trading ticket system fully functional with 8 interactive buttons

- **Dec 2024**: Fixed trade creation bug and improved announcements
  - Fixed critical bug where trade creation was silently failing
  - Trade announcements now show the item's image as thumbnail (not user avatar)
  - Fixed type compatibility issues across the codebase
  - All button interactions now properly typed and error-free

- **Dec 2024**: Fixed /item command and improved database population
  - Database now auto-populates from fallback data on startup if empty
  - Added `/owner refresh_cache` - Fetches items from APIs and saves to database
  - Added `/owner load_fallback` - Manually load fallback data into database
  - Fixed item resolution to work correctly with database items
  - Bot now shows item count in `/owner status`
  - 138 items pre-loaded across all 5 games

- **Dec 2024**: Added direct image upload support
  - All item management commands now support uploading images directly from your device
  - Simply attach an image when using `/manage add`, `/manage update`, or `/manage setimage`
  - Supports PNG, JPEG, GIF, and WebP formats (max 8MB)
  - Image validation ensures only valid image files are accepted
  - Can still use image URLs as an alternative to uploading

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

- **Dec 2024**: Added Trade Ticket System
  - When a trade is accepted, a private thread is created for the traders
  - Both traders are automatically added and pinged in the thread
  - Thread includes 8 interactive buttons:
    - Share Roblox Username (modal with profile link)
    - Confirm Trade Complete (both must confirm)
    - Safety Checklist (before/during/after checklist)
    - View Trade Items (shows all items and values)
    - Upload Proof (instructions for screenshots)
    - Invite Moderator (pings mod role)
    - Report Issue (flags trade as disputed)
    - Close Ticket (archives the thread)
  - Threads auto-archive after trade completion
  - Server admins can now use `/manage` commands (not just bot owner)

- **Dec 2024**: GitHub & Railway Deployment Ready
  - Added README.md, requirements.txt, LICENSE, Procfile, runtime.txt, railway.json
  - Bot runs on Railway 24/7 without keep_alive server
