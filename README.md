# Roblox Trading Discord Bot

A production-grade Discord bot for secure Roblox trading coordination across multiple games.

## Supported Games

- **Pet Simulator 99** (PS99)
- **Grow a Garden** (GAG)
- **Adopt Me** (AM)
- **Blox Fruits** (BF)
- **Steal a Brainrot** (SAB)

## Features

- **Manual Item Management**: Full control over items via Discord commands
- **Trade Lifecycle**: Complete trade flow from draft to completion with verification
- **Trust Engine**: Calculates trust scores based on account age, trade history, and disputes
- **Item Resolution**: Database lookup with alias matching and fuzzy search
- **Anti-Scam Protection**: Detects lowball spam, pressure tactics, and bait-and-switch attempts
- **Immutable Receipts**: SHA-256 hashed trade records for verification
- **Auction System**: Create and bid on item auctions
- **Image Upload Support**: Upload item images directly (PNG, JPEG, GIF, WebP up to 8MB)

## Installation

### Prerequisites

- Python 3.11 or higher
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/roblox-trading-bot.git
   cd roblox-trading-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or using pip with pyproject.toml:
   ```bash
   pip install .
   ```

3. **Configure environment variables**
   
   Create a `.env` file in the project root:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   ```

4. **Run the bot**
   ```bash
   python main.py
   ```

## Project Structure

```
/
├── main.py              # Bot entry point
├── keep_alive.py        # Flask server for uptime (optional)
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
├── api/                 # Game API adapters
├── ui/                  # Discord UI components
│   ├── embeds.py        # Message embeds
│   ├── views.py         # Button/select views
│   └── modals.py        # Input modals
├── utils/               # Utility modules
│   ├── database.py      # SQLite database operations
│   ├── cache.py         # Caching system
│   ├── fuzzy.py         # Fuzzy string matching
│   ├── resolver.py      # Item resolution
│   ├── validators.py    # Input validation
│   ├── rate_limit.py    # Rate limiting
│   └── trust_engine.py  # Trust scoring system
├── data/                # Database storage
└── locales/             # Internationalization
```

## Commands

### Trading Commands
| Command | Description |
|---------|-------------|
| `/trade create` | Create a trade offer |
| `/trade view` | View trade details |
| `/trade history` | View trade history |
| `/trade cancel` | Cancel a pending trade |
| `/trade verify` | Verify trade receipt by hash |

### Auction Commands
| Command | Description |
|---------|-------------|
| `/auction create` | Create a new auction |
| `/auction bid` | Place a bid on an auction |
| `/auction list` | List active auctions |
| `/auction view` | View auction details |
| `/auction cancel` | Cancel your auction |

### Inventory & Profile
| Command | Description |
|---------|-------------|
| `/inventory view` | View inventory |
| `/inventory add` | Add item to inventory |
| `/profile` | View trading profile |
| `/link_roblox` | Link Roblox account |
| `/search` | Search for items |
| `/item` | Get item details |
| `/values` | View top valued items |

### Item Management (Owner Only)
| Command | Description |
|---------|-------------|
| `/manage add` | Add a new item |
| `/manage update` | Update an existing item |
| `/manage setvalue` | Update an item's value |
| `/manage setimage` | Set or update item image |
| `/manage delete` | Remove an item |
| `/manage list` | View all items for a game |
| `/manage bulkvalue` | Bulk update item values (JSON) |

### Moderation Commands
| Command | Description |
|---------|-------------|
| `/mod audit_trade` | View detailed trade audit log |
| `/mod force_resolve` | Force resolve a disputed trade |
| `/mod ban_user` | Ban a user from trading |
| `/mod unban_user` | Unban a user |
| `/mod rollback_rep` | Reset user reputation |
| `/mod flag_user` | Flag a user for review |
| `/mod replay_trade` | View visual timeline of a trade |

### Settings (Admin)
| Command | Description |
|---------|-------------|
| `/settings tradechannel` | Set trade announcement channel |
| `/settings logchannel` | Set logging channel |
| `/settings modrole` | Set moderator role |
| `/settings toggle` | Toggle bot features |
| `/settings mintrust` | Set minimum trust level |
| `/settings view` | View current settings |

## Tech Stack

- **Python 3.11+**
- **discord.py 2.6+** - Discord API wrapper
- **aiohttp** - Async HTTP client
- **aiosqlite** - Async SQLite database
- **Flask** - Keep-alive server
- **python-Levenshtein** - Fuzzy string matching

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_TOKEN` | Your Discord bot token | Yes |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Deployment

### Deploy to Railway

1. **Push your code to GitHub** (see above)

2. **Create a Railway account** at [railway.app](https://railway.app)

3. **Create a new project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

4. **Add environment variables**
   - Go to your project's "Variables" tab
   - Add: `DISCORD_TOKEN` = your bot token

5. **Deploy**
   - Railway will automatically detect Python and deploy
   - Your bot will be online 24/7!

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Your Discord bot token (required) |

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

If you encounter any issues or have questions, please open an issue on GitHub.
