import aiosqlite
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DATABASE_PATH = "data/trading_bot.db"

async def init_database():
    os.makedirs("data", exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                discord_id INTEGER PRIMARY KEY,
                roblox_username TEXT,
                roblox_id INTEGER,
                roblox_account_age INTEGER,
                discord_account_created TEXT,
                trust_score REAL DEFAULT 50.0,
                trust_tier TEXT DEFAULT 'Bronze',
                reliability REAL DEFAULT 50.0,
                fairness REAL DEFAULT 50.0,
                responsiveness REAL DEFAULT 50.0,
                proof_compliance REAL DEFAULT 50.0,
                total_trades INTEGER DEFAULT 0,
                successful_trades INTEGER DEFAULT 0,
                disputed_trades INTEGER DEFAULT 0,
                cancelled_trades INTEGER DEFAULT 0,
                total_value_traded REAL DEFAULT 0.0,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game TEXT NOT NULL,
                item_id TEXT NOT NULL,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                rarity TEXT,
                icon_url TEXT,
                value REAL,
                tradeable INTEGER DEFAULT 1,
                source TEXT,
                metadata TEXT,
                last_verified TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(game, item_id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS item_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game TEXT NOT NULL,
                item_id TEXT NOT NULL,
                alias TEXT NOT NULL,
                UNIQUE(game, alias)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_hash TEXT UNIQUE,
                requester_id INTEGER NOT NULL,
                target_id INTEGER,
                game TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                risk_level TEXT DEFAULT 'unknown',
                requester_items TEXT,
                target_items TEXT,
                requester_confirmed INTEGER DEFAULT 0,
                target_confirmed INTEGER DEFAULT 0,
                proof_url TEXT,
                receipt_hash TEXT,
                moderator_notes TEXT,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                archived_at TEXT
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor_id INTEGER NOT NULL,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trade_id) REFERENCES trades(id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS inventories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                for_trade INTEGER DEFAULT 0,
                wishlist INTEGER DEFAULT 0,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, game, item_id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                reported_id INTEGER NOT NULL,
                trade_id INTEGER,
                reason TEXT NOT NULL,
                evidence TEXT,
                status TEXT DEFAULT 'pending',
                moderator_id INTEGER,
                resolution TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS scam_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                pattern_type TEXT NOT NULL,
                occurrences INTEGER DEFAULT 1,
                last_occurrence TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, pattern_type)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                actor_id INTEGER,
                target_id INTEGER,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS auctions (
                id TEXT PRIMARY KEY,
                seller_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                item_data TEXT NOT NULL,
                starting_bid INTEGER NOT NULL,
                current_bid INTEGER DEFAULT 0,
                current_bidder INTEGER,
                status TEXT DEFAULT 'active',
                channel_id INTEGER,
                message_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                ends_at TEXT NOT NULL
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS auction_bids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auction_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (auction_id) REFERENCES auctions(id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS game_sources (
                game TEXT PRIMARY KEY,
                values_url TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER
            )
        ''')
        
        await db.execute('CREATE INDEX IF NOT EXISTS idx_items_game ON items(game)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_items_normalized ON items(normalized_name)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_trades_users ON trades(requester_id, target_id)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_inventories_user ON inventories(user_id)')
        
        await db.commit()

async def get_db():
    return await aiosqlite.connect(DATABASE_PATH)

async def get_user(discord_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE discord_id = ?', (discord_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def create_user(discord_id: int, discord_created: str) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            INSERT OR IGNORE INTO users (discord_id, discord_account_created)
            VALUES (?, ?)
        ''', (discord_id, discord_created))
        await db.commit()
    return await get_user(discord_id)

async def update_user(discord_id: int, **kwargs) -> None:
    if not kwargs:
        return
    fields = ', '.join(f'{k} = ?' for k in kwargs.keys())
    values = list(kwargs.values()) + [discord_id]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(f'UPDATE users SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE discord_id = ?', values)
        await db.commit()

async def get_trade(trade_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM trades WHERE id = ?', (trade_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def create_trade(requester_id: int, game: str, requester_items: str) -> Optional[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO trades (requester_id, game, requester_items, status)
            VALUES (?, ?, ?, 'draft')
        ''', (requester_id, game, requester_items))
        await db.commit()
        return cursor.lastrowid

async def update_trade(trade_id: int, **kwargs) -> None:
    if not kwargs:
        return
    fields = ', '.join(f'{k} = ?' for k in kwargs.keys())
    values = list(kwargs.values()) + [trade_id]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(f'UPDATE trades SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', values)
        await db.commit()

async def add_trade_history(trade_id: int, action: str, actor_id: int, details: Optional[str] = None) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            INSERT INTO trade_history (trade_id, action, actor_id, details)
            VALUES (?, ?, ?, ?)
        ''', (trade_id, action, actor_id, details))
        await db.commit()

async def get_user_trades(user_id: int, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            query = 'SELECT * FROM trades WHERE (requester_id = ? OR target_id = ?) AND status = ? ORDER BY updated_at DESC LIMIT ?'
            params = (user_id, user_id, status, limit)
        else:
            query = 'SELECT * FROM trades WHERE requester_id = ? OR target_id = ? ORDER BY updated_at DESC LIMIT ?'
            params = (user_id, user_id, limit)
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_inventory(user_id: int, game: Optional[str] = None) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if game:
            query = '''
                SELECT i.*, it.name, it.rarity, it.icon_url, it.value 
                FROM inventories i 
                LEFT JOIN items it ON i.game = it.game AND i.item_id = it.item_id
                WHERE i.user_id = ? AND i.game = ?
            '''
            params = (user_id, game)
        else:
            query = '''
                SELECT i.*, it.name, it.rarity, it.icon_url, it.value 
                FROM inventories i 
                LEFT JOIN items it ON i.game = it.game AND i.item_id = it.item_id
                WHERE i.user_id = ?
            '''
            params = (user_id,)
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def add_to_inventory(user_id: int, game: str, item_id: str, quantity: int = 1) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            INSERT INTO inventories (user_id, game, item_id, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, game, item_id) DO UPDATE SET quantity = quantity + ?
        ''', (user_id, game, item_id, quantity, quantity))
        await db.commit()

async def remove_from_inventory(user_id: int, game: str, item_id: str, quantity: int = 1) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            'SELECT quantity FROM inventories WHERE user_id = ? AND game = ? AND item_id = ?',
            (user_id, game, item_id)
        ) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < quantity:
                return False
        
        if row[0] == quantity:
            await db.execute(
                'DELETE FROM inventories WHERE user_id = ? AND game = ? AND item_id = ?',
                (user_id, game, item_id)
            )
        else:
            await db.execute(
                'UPDATE inventories SET quantity = quantity - ? WHERE user_id = ? AND game = ? AND item_id = ?',
                (quantity, user_id, game, item_id)
            )
        await db.commit()
        return True

async def log_audit(action: str, actor_id: Optional[int] = None, target_id: Optional[int] = None, details: Optional[str] = None) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            INSERT INTO audit_log (action, actor_id, target_id, details)
            VALUES (?, ?, ?, ?)
        ''', (action, actor_id, target_id, details))
        await db.commit()

async def record_scam_pattern(user_id: int, pattern_type: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            INSERT INTO scam_patterns (user_id, pattern_type)
            VALUES (?, ?)
            ON CONFLICT(user_id, pattern_type) DO UPDATE SET 
                occurrences = occurrences + 1,
                last_occurrence = CURRENT_TIMESTAMP
        ''', (user_id, pattern_type))
        await db.commit()
        async with db.execute(
            'SELECT occurrences FROM scam_patterns WHERE user_id = ? AND pattern_type = ?',
            (user_id, pattern_type)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 1

async def get_item(game: str, item_id: str) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM items WHERE game = ? AND item_id = ?', (game, item_id)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def search_items(game: str, query: str, limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        normalized = query.lower().replace(' ', '').replace('-', '').replace('_', '')
        async with db.execute('''
            SELECT * FROM items 
            WHERE game = ? AND (
                normalized_name LIKE ? OR
                name LIKE ?
            )
            LIMIT ?
        ''', (game, f'%{normalized}%', f'%{query}%', limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def upsert_item(game: str, item_id: str, name: str, **kwargs) -> None:
    normalized = name.lower().replace(' ', '').replace('-', '').replace('_', '')
    async with aiosqlite.connect(DATABASE_PATH) as db:
        existing = await get_item(game, item_id)
        if existing:
            fields = ', '.join(f'{k} = ?' for k in kwargs.keys())
            if fields:
                values = list(kwargs.values()) + [game, item_id]
                await db.execute(f'UPDATE items SET {fields}, last_verified = CURRENT_TIMESTAMP WHERE game = ? AND item_id = ?', values)
        else:
            columns = ['game', 'item_id', 'name', 'normalized_name'] + list(kwargs.keys())
            placeholders = ', '.join(['?'] * len(columns))
            values = [game, item_id, name, normalized] + list(kwargs.values())
            await db.execute(f'INSERT INTO items ({", ".join(columns)}) VALUES ({placeholders})', values)
        await db.commit()

async def get_game_source(game: str) -> Optional[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute('SELECT values_url FROM game_sources WHERE game = ?', (game,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def set_game_source(game: str, values_url: str, updated_by: Optional[int] = None) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            INSERT INTO game_sources (game, values_url, updated_by, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(game) DO UPDATE SET 
                values_url = excluded.values_url,
                updated_by = excluded.updated_by,
                updated_at = CURRENT_TIMESTAMP
        ''', (game, values_url, updated_by))
        await db.commit()

async def get_all_game_sources() -> Dict[str, str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT game, values_url FROM game_sources') as cursor:
            rows = await cursor.fetchall()
            return {row['game']: row['values_url'] for row in rows}


async def delete_item(game: str, item_id: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM items WHERE game = ? AND item_id = ?',
            (game, item_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_all_items_for_game(game: str, limit: int = 100) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM items WHERE game = ? ORDER BY value DESC LIMIT ?',
            (game, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_item_field(game: str, item_id: str, field: str, value: Any) -> bool:
    allowed_fields = {'name', 'normalized_name', 'rarity', 'icon_url', 'value', 'tradeable', 'source', 'metadata'}
    if field not in allowed_fields:
        raise ValueError(f"Field '{field}' is not allowed to be updated")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if field == 'name':
            normalized = str(value).lower().replace(' ', '').replace('-', '').replace('_', '')
            cursor = await db.execute(
                'UPDATE items SET name = ?, normalized_name = ?, last_verified = CURRENT_TIMESTAMP WHERE game = ? AND item_id = ?',
                (value, normalized, game, item_id)
            )
        else:
            cursor = await db.execute(
                f'UPDATE items SET {field} = ?, last_verified = CURRENT_TIMESTAMP WHERE game = ? AND item_id = ?',
                (value, game, item_id)
            )
        await db.commit()
        return cursor.rowcount > 0
