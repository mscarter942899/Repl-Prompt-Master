import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any

DATABASE_PATH = "data/trading_bot.db"


async def init_enhanced_tables():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS wishlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                item_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                max_price REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, game, item_id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS lf_ft_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                post_type TEXT NOT NULL,
                items TEXT NOT NULL,
                gems INTEGER DEFAULT 0,
                notes TEXT,
                status TEXT DEFAULT 'active',
                message_id INTEGER,
                channel_id INTEGER,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trader_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reviewer_id INTEGER NOT NULL,
                reviewed_id INTEGER NOT NULL,
                trade_id INTEGER,
                rating INTEGER NOT NULL,
                review_text TEXT,
                review_type TEXT DEFAULT 'positive',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(reviewer_id, trade_id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS favorite_traders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                favorite_id INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, favorite_id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS blocked_traders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                blocked_id INTEGER NOT NULL,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, blocked_id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trade_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                game TEXT NOT NULL,
                offering_items TEXT,
                requesting_items TEXT,
                offering_gems INTEGER DEFAULT 0,
                requesting_gems INTEGER DEFAULT 0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trade_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                trigger_type TEXT NOT NULL,
                game TEXT,
                item_id TEXT,
                min_value REAL,
                max_value REAL,
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trade_feed_settings (
                guild_id INTEGER PRIMARY KEY,
                feed_channel_id INTEGER,
                show_item_images INTEGER DEFAULT 1,
                show_values INTEGER DEFAULT 1,
                show_trader_info INTEGER DEFAULT 1,
                min_trade_value REAL DEFAULT 0,
                games_filter TEXT,
                enabled INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trade_stats (
                user_id INTEGER PRIMARY KEY,
                total_value_given REAL DEFAULT 0,
                total_value_received REAL DEFAULT 0,
                total_gems_traded REAL DEFAULT 0,
                biggest_trade_value REAL DEFAULT 0,
                favorite_game TEXT,
                most_traded_item TEXT,
                trade_streak INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN offering_gems INTEGER DEFAULT 0')
        except:
            pass
        
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN requesting_gems INTEGER DEFAULT 0')
        except:
            pass
        
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN notes TEXT')
        except:
            pass
        
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN counter_offer_data TEXT')
        except:
            pass
        
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN requester_locked INTEGER DEFAULT 0')
        except:
            pass
        
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN target_locked INTEGER DEFAULT 0')
        except:
            pass
        
        await db.execute('CREATE INDEX IF NOT EXISTS idx_wishlists_user ON wishlists(user_id)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_lf_ft_posts_guild ON lf_ft_posts(guild_id, status)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_reviews_reviewed ON trader_reviews(reviewed_id)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user ON trade_notifications(user_id)')
        
        await db.commit()


async def add_to_wishlist(user_id: int, game: str, item_id: str, item_name: str, 
                          priority: int = 1, max_price: Optional[float] = None, notes: Optional[str] = None) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute('''
                INSERT INTO wishlists (user_id, game, item_id, item_name, priority, max_price, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, game, item_id) DO UPDATE SET
                    priority = excluded.priority,
                    max_price = excluded.max_price,
                    notes = excluded.notes
            ''', (user_id, game, item_id, item_name, priority, max_price, notes))
            await db.commit()
            return True
        except Exception:
            return False


async def remove_from_wishlist(user_id: int, game: str, item_id: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM wishlists WHERE user_id = ? AND game = ? AND item_id = ?',
            (user_id, game, item_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_wishlist(user_id: int, game: Optional[str] = None) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if game:
            query = 'SELECT * FROM wishlists WHERE user_id = ? AND game = ? ORDER BY priority DESC'
            params = (user_id, game)
        else:
            query = 'SELECT * FROM wishlists WHERE user_id = ? ORDER BY priority DESC'
            params = (user_id,)
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def create_lf_ft_post(user_id: int, guild_id: int, game: str, post_type: str,
                            items: List[Dict], gems: int = 0, notes: Optional[str] = None,
                            expires_hours: int = 24) -> Optional[int]:
    import json
    from datetime import timedelta
    
    expires_at = (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO lf_ft_posts (user_id, guild_id, game, post_type, items, gems, notes, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, guild_id, game, post_type, json.dumps(items), gems, notes, expires_at))
        await db.commit()
        return cursor.lastrowid


async def get_active_lf_ft_posts(guild_id: int, game: Optional[str] = None, 
                                  post_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
    import json
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        query = 'SELECT * FROM lf_ft_posts WHERE guild_id = ? AND status = ? AND expires_at > ?'
        params = [guild_id, 'active', datetime.utcnow().isoformat()]
        
        if game:
            query += ' AND game = ?'
            params.append(game)
        if post_type:
            query += ' AND post_type = ?'
            params.append(post_type)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            posts = []
            for row in rows:
                post = dict(row)
                post['items'] = json.loads(post['items']) if post['items'] else []
                posts.append(post)
            return posts


async def add_trader_review(reviewer_id: int, reviewed_id: int, trade_id: int,
                            rating: int, review_text: Optional[str] = None) -> bool:
    review_type = 'positive' if rating >= 4 else ('neutral' if rating >= 3 else 'negative')
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute('''
                INSERT INTO trader_reviews (reviewer_id, reviewed_id, trade_id, rating, review_text, review_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (reviewer_id, reviewed_id, trade_id, rating, review_text, review_type))
            await db.commit()
            return True
        except Exception:
            return False


async def get_trader_reviews(user_id: int, limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM trader_reviews WHERE reviewed_id = ? 
            ORDER BY created_at DESC LIMIT ?
        ''', (user_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_trader_rating_summary(user_id: int) -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute('''
            SELECT 
                COUNT(*) as total,
                AVG(rating) as average,
                SUM(CASE WHEN review_type = 'positive' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN review_type = 'neutral' THEN 1 ELSE 0 END) as neutral,
                SUM(CASE WHEN review_type = 'negative' THEN 1 ELSE 0 END) as negative
            FROM trader_reviews WHERE reviewed_id = ?
        ''', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    'total': row[0] or 0,
                    'average': row[1] or 0,
                    'positive': row[2] or 0,
                    'neutral': row[3] or 0,
                    'negative': row[4] or 0
                }
            return {'total': 0, 'average': 0, 'positive': 0, 'neutral': 0, 'negative': 0}


async def add_favorite_trader(user_id: int, favorite_id: int, notes: Optional[str] = None) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute('''
                INSERT INTO favorite_traders (user_id, favorite_id, notes)
                VALUES (?, ?, ?)
            ''', (user_id, favorite_id, notes))
            await db.commit()
            return True
        except Exception:
            return False


async def remove_favorite_trader(user_id: int, favorite_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM favorite_traders WHERE user_id = ? AND favorite_id = ?',
            (user_id, favorite_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_favorite_traders(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM favorite_traders WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def block_trader(user_id: int, blocked_id: int, reason: Optional[str] = None) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute('''
                INSERT INTO blocked_traders (user_id, blocked_id, reason)
                VALUES (?, ?, ?)
            ''', (user_id, blocked_id, reason))
            await db.commit()
            return True
        except Exception:
            return False


async def unblock_trader(user_id: int, blocked_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM blocked_traders WHERE user_id = ? AND blocked_id = ?',
            (user_id, blocked_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def is_trader_blocked(user_id: int, other_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            'SELECT 1 FROM blocked_traders WHERE user_id = ? AND blocked_id = ?',
            (user_id, other_id)
        ) as cursor:
            return await cursor.fetchone() is not None


async def get_blocked_traders(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM blocked_traders WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def save_trade_template(user_id: int, name: str, game: str, 
                              offering_items: List[Dict], requesting_items: List[Dict],
                              offering_gems: int = 0, requesting_gems: int = 0,
                              notes: Optional[str] = None) -> bool:
    import json
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute('''
                INSERT INTO trade_templates (user_id, name, game, offering_items, requesting_items, 
                                            offering_gems, requesting_gems, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, name) DO UPDATE SET
                    game = excluded.game,
                    offering_items = excluded.offering_items,
                    requesting_items = excluded.requesting_items,
                    offering_gems = excluded.offering_gems,
                    requesting_gems = excluded.requesting_gems,
                    notes = excluded.notes
            ''', (user_id, name, game, json.dumps(offering_items), json.dumps(requesting_items),
                  offering_gems, requesting_gems, notes))
            await db.commit()
            return True
        except Exception:
            return False


async def get_trade_templates(user_id: int, game: Optional[str] = None) -> List[Dict]:
    import json
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if game:
            query = 'SELECT * FROM trade_templates WHERE user_id = ? AND game = ? ORDER BY name'
            params = (user_id, game)
        else:
            query = 'SELECT * FROM trade_templates WHERE user_id = ? ORDER BY name'
            params = (user_id,)
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            templates = []
            for row in rows:
                template = dict(row)
                template['offering_items'] = json.loads(template['offering_items']) if template['offering_items'] else []
                template['requesting_items'] = json.loads(template['requesting_items']) if template['requesting_items'] else []
                templates.append(template)
            return templates


async def delete_trade_template(user_id: int, name: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM trade_templates WHERE user_id = ? AND name = ?',
            (user_id, name)
        )
        await db.commit()
        return cursor.rowcount > 0


async def set_trade_feed_settings(guild_id: int, **kwargs) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        existing = None
        async with db.execute('SELECT 1 FROM trade_feed_settings WHERE guild_id = ?', (guild_id,)) as cursor:
            existing = await cursor.fetchone()
        
        if existing:
            if kwargs:
                fields = ', '.join(f'{k} = ?' for k in kwargs.keys())
                values = list(kwargs.values()) + [guild_id]
                await db.execute(f'UPDATE trade_feed_settings SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?', values)
        else:
            columns = ['guild_id'] + list(kwargs.keys())
            placeholders = ', '.join(['?'] * len(columns))
            values = [guild_id] + list(kwargs.values())
            await db.execute(f'INSERT INTO trade_feed_settings ({", ".join(columns)}) VALUES ({placeholders})', values)
        await db.commit()


async def get_trade_feed_settings(guild_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM trade_feed_settings WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_trade_leaderboard(guild_id: Optional[int] = None, limit: int = 10, 
                                 metric: str = 'total_trades') -> List[Dict]:
    from utils.database import DATABASE_PATH
    
    valid_metrics = {
        'total_trades': 'total_trades',
        'successful_trades': 'successful_trades', 
        'trust_score': 'trust_score',
        'total_value_traded': 'total_value_traded'
    }
    
    order_column = valid_metrics.get(metric, 'total_trades')
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f'''
            SELECT discord_id, trust_score, trust_tier, total_trades, 
                   successful_trades, total_value_traded
            FROM users 
            WHERE is_banned = 0 AND total_trades > 0
            ORDER BY {order_column} DESC 
            LIMIT ?
        ''', (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_trade_stats(user_id: int, value_given: float = 0, value_received: float = 0,
                             gems_traded: float = 0) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            INSERT INTO trade_stats (user_id, total_value_given, total_value_received, total_gems_traded)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                total_value_given = total_value_given + ?,
                total_value_received = total_value_received + ?,
                total_gems_traded = total_gems_traded + ?,
                biggest_trade_value = MAX(biggest_trade_value, ?),
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, value_given, value_received, gems_traded, 
              value_given, value_received, gems_traded, max(value_given, value_received)))
        await db.commit()


async def find_matching_trades(user_id: int, game: str, looking_for: List[str]) -> List[Dict]:
    import json
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        async with db.execute('''
            SELECT * FROM trades 
            WHERE game = ? AND status = 'pending' AND requester_id != ? AND target_id IS NULL
            ORDER BY created_at DESC
            LIMIT 50
        ''', (game, user_id)) as cursor:
            rows = await cursor.fetchall()
            
            matches = []
            for row in rows:
                trade = dict(row)
                requester_items = json.loads(trade.get('requester_items', '[]'))
                item_names = [item.get('name', '').lower() for item in requester_items]
                
                for wanted in looking_for:
                    if wanted.lower() in item_names:
                        matches.append(trade)
                        break
            
            return matches


async def check_wishlist_matches(game: str, offered_items: List[Dict]) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        item_ids = [item.get('id', '') for item in offered_items]
        if not item_ids:
            return []
        
        placeholders = ','.join(['?'] * len(item_ids))
        async with db.execute(f'''
            SELECT * FROM wishlists 
            WHERE game = ? AND item_id IN ({placeholders})
        ''', [game] + item_ids) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
