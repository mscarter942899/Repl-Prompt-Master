import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional
import json
import aiosqlite
from datetime import datetime, timedelta

from utils.database import DATABASE_PATH, log_audit
from utils.resolver import item_resolver
from utils.rate_limit import rate_limiter
from ui.embeds import GAME_NAMES, GAME_COLORS


class AuctionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_auctions.start()
    
    def cog_unload(self):
        self.check_auctions.cancel()
    
    @tasks.loop(minutes=1)
    async def check_auctions(self):
        now = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM auctions WHERE status = 'active' AND ends_at <= ?",
                (now,)
            ) as cursor:
                expired = await cursor.fetchall()
        
        for auction in expired:
            await self._end_auction(dict(auction))
    
    @check_auctions.before_loop
    async def before_check_auctions(self):
        await self.bot.wait_until_ready()
    
    async def _get_auction(self, auction_id: str) -> Optional[dict]:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def _create_auction(self, auction_id: str, seller_id: int, game: str, item: dict,
                              starting_bid: int, ends_at: str, channel_id: Optional[int]) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute('''
                INSERT INTO auctions (id, seller_id, game, item_data, starting_bid, ends_at, channel_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (auction_id, seller_id, game, json.dumps(item), starting_bid, ends_at, channel_id))
            await db.commit()
    
    async def _update_auction(self, auction_id: str, **kwargs) -> None:
        if not kwargs:
            return
        fields = ', '.join(f'{k} = ?' for k in kwargs.keys())
        values = list(kwargs.values()) + [auction_id]
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(f'UPDATE auctions SET {fields} WHERE id = ?', values)
            await db.commit()
    
    async def _add_bid(self, auction_id: str, user_id: int, amount: int) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute('''
                INSERT INTO auction_bids (auction_id, user_id, amount)
                VALUES (?, ?, ?)
            ''', (auction_id, user_id, amount))
            await db.commit()
    
    async def _get_auction_bids(self, auction_id: str, limit: int = 5):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM auction_bids WHERE auction_id = ? ORDER BY timestamp DESC LIMIT ?",
                (auction_id, limit)
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]
    
    auction_group = app_commands.Group(name="auction", description="Auction commands")
    
    @auction_group.command(name="create", description="Create a new auction")
    @app_commands.describe(
        game="The game for this auction",
        item="The item you're auctioning",
        starting_bid="Minimum starting bid",
        duration="Auction duration in hours (1-72)"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def auction_create(
        self, 
        interaction: discord.Interaction, 
        game: str, 
        item: str,
        starting_bid: int,
        duration: int = 24
    ):
        allowed, retry_after = await rate_limiter.check(interaction.user.id, 'auction_create')
        if not allowed:
            await interaction.response.send_message(
                f"You're creating auctions too fast. Please wait {retry_after} seconds.",
                ephemeral=True
            )
            return
        
        if duration < 1 or duration > 72:
            await interaction.response.send_message("Duration must be between 1 and 72 hours.", ephemeral=True)
            return
        
        if starting_bid < 0:
            await interaction.response.send_message("Starting bid must be positive.", ephemeral=True)
            return
        
        resolved_item = await item_resolver.resolve_item(game, item)
        if not resolved_item:
            suggestions = await item_resolver.suggest_items(game, item, limit=3)
            if suggestions:
                suggestion_text = ', '.join([s['name'] for s in suggestions])
                await interaction.response.send_message(
                    f"Item '{item}' not found. Did you mean: {suggestion_text}?",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(f"Item '{item}' not found.", ephemeral=True)
            return
        
        auction_id = f"{interaction.user.id}_{int(datetime.utcnow().timestamp())}"
        ends_at = (datetime.utcnow() + timedelta(hours=duration)).isoformat()
        
        await self._create_auction(
            auction_id, interaction.user.id, game, resolved_item,
            starting_bid, ends_at, interaction.channel_id if interaction.channel else None
        )
        
        auction = await self._get_auction(auction_id)
        if auction:
            embed = self._create_auction_embed(auction, interaction.user)
            await interaction.response.send_message(embed=embed)
            msg = await interaction.original_response()
            await self._update_auction(auction_id, message_id=msg.id)
        
        await log_audit('auction_created', interaction.user.id, None, f"Auction {auction_id}")
    
    @auction_group.command(name="bid", description="Place a bid on an auction")
    @app_commands.describe(auction_id="The auction ID", amount="Your bid amount")
    async def auction_bid(self, interaction: discord.Interaction, auction_id: str, amount: int):
        auction = await self._get_auction(auction_id)
        
        if not auction:
            await interaction.response.send_message("Auction not found.", ephemeral=True)
            return
        
        if auction['status'] != 'active':
            await interaction.response.send_message("This auction has ended.", ephemeral=True)
            return
        
        if auction['seller_id'] == interaction.user.id:
            await interaction.response.send_message("You cannot bid on your own auction.", ephemeral=True)
            return
        
        if datetime.fromisoformat(auction['ends_at']) <= datetime.utcnow():
            await interaction.response.send_message("This auction has expired.", ephemeral=True)
            return
        
        min_bid = max(auction['starting_bid'], auction['current_bid'] + 1)
        if amount < min_bid:
            await interaction.response.send_message(
                f"Minimum bid is {min_bid}. Current highest bid: {auction['current_bid']}",
                ephemeral=True
            )
            return
        
        previous_bidder = auction['current_bidder']
        
        await self._update_auction(auction_id, current_bid=amount, current_bidder=interaction.user.id)
        await self._add_bid(auction_id, interaction.user.id, amount)
        
        ends = datetime.fromisoformat(auction['ends_at'])
        time_left = (ends - datetime.utcnow()).total_seconds()
        if time_left < 300:
            new_ends = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            await self._update_auction(auction_id, ends_at=new_ends)
        
        await interaction.response.send_message(f"Bid of {amount:,} placed successfully!", ephemeral=True)
        
        if previous_bidder and previous_bidder != interaction.user.id:
            try:
                prev_user = await self.bot.fetch_user(previous_bidder)
                await prev_user.send(f"You've been outbid on auction {auction_id}! New highest bid: {amount:,}")
            except:
                pass
    
    @auction_group.command(name="list", description="List active auctions")
    @app_commands.describe(game="Filter by game")
    @app_commands.choices(game=[
        app_commands.Choice(name="All Games", value="all"),
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def auction_list(self, interaction: discord.Interaction, game: str = "all"):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            if game == "all":
                async with db.execute("SELECT * FROM auctions WHERE status = 'active' ORDER BY ends_at ASC LIMIT 10") as cursor:
                    auctions = [dict(row) for row in await cursor.fetchall()]
            else:
                async with db.execute("SELECT * FROM auctions WHERE status = 'active' AND game = ? ORDER BY ends_at ASC LIMIT 10", (game,)) as cursor:
                    auctions = [dict(row) for row in await cursor.fetchall()]
        
        if not auctions:
            await interaction.response.send_message("No active auctions found.", ephemeral=True)
            return
        
        embed = discord.Embed(title="Active Auctions", color=0xF39C12, timestamp=datetime.utcnow())
        
        for auction in auctions:
            item = json.loads(auction['item_data'])
            item_name = item.get('name', 'Unknown')
            game_name = GAME_NAMES.get(auction['game'], auction['game'].upper())
            current = auction['current_bid'] if auction['current_bid'] > 0 else auction['starting_bid']
            ends = datetime.fromisoformat(auction['ends_at'])
            time_left = ends - datetime.utcnow()
            hours_left = max(0, int(time_left.total_seconds() // 3600))
            mins_left = max(0, int((time_left.total_seconds() % 3600) // 60))
            
            embed.add_field(
                name=f"{item_name} ({game_name})",
                value=f"Current Bid: {current:,}\nEnds in: {hours_left}h {mins_left}m\nID: `{auction['id'][:20]}...`",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)
    
    @auction_group.command(name="cancel", description="Cancel your auction")
    @app_commands.describe(auction_id="The auction ID to cancel")
    async def auction_cancel(self, interaction: discord.Interaction, auction_id: str):
        auction = await self._get_auction(auction_id)
        
        if not auction:
            await interaction.response.send_message("Auction not found.", ephemeral=True)
            return
        
        if auction['seller_id'] != interaction.user.id:
            await interaction.response.send_message("You can only cancel your own auctions.", ephemeral=True)
            return
        
        if auction['current_bid'] > 0:
            await interaction.response.send_message(
                "Cannot cancel an auction with active bids.",
                ephemeral=True
            )
            return
        
        await self._update_auction(auction_id, status='cancelled')
        await log_audit('auction_cancelled', interaction.user.id, None, f"Auction {auction_id}")
        await interaction.response.send_message(f"Auction {auction_id} has been cancelled.")
    
    @auction_group.command(name="view", description="View auction details")
    @app_commands.describe(auction_id="The auction ID to view")
    async def auction_view(self, interaction: discord.Interaction, auction_id: str):
        auction = await self._get_auction(auction_id)
        
        if not auction:
            await interaction.response.send_message("Auction not found.", ephemeral=True)
            return
        
        seller = await self.bot.fetch_user(auction['seller_id'])
        embed = self._create_auction_embed(auction, seller)
        
        bids = await self._get_auction_bids(auction_id, 5)
        if bids:
            bid_history = []
            for bid in bids:
                try:
                    bidder = await self.bot.fetch_user(bid['user_id'])
                    bid_history.append(f"{bidder.display_name}: {bid['amount']:,}")
                except:
                    bid_history.append(f"User: {bid['amount']:,}")
            embed.add_field(name="Recent Bids", value="\n".join(bid_history), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    async def _end_auction(self, auction: dict):
        await self._update_auction(auction['id'], status='ended')
        
        try:
            seller = await self.bot.fetch_user(auction['seller_id'])
            item = json.loads(auction['item_data'])
            
            if auction['current_bidder']:
                winner = await self.bot.fetch_user(auction['current_bidder'])
                await seller.send(
                    f"Your auction for **{item['name']}** has ended!\n"
                    f"Winner: {winner.display_name}\n"
                    f"Winning bid: {auction['current_bid']:,}\n"
                    f"Please coordinate the in-game trade with the winner."
                )
                await winner.send(
                    f"Congratulations! You won the auction for **{item['name']}**!\n"
                    f"Your winning bid: {auction['current_bid']:,}\n"
                    f"Please contact {seller.display_name} to complete the trade in-game."
                )
            else:
                await seller.send(f"Your auction for **{item['name']}** has ended with no bids.")
        except Exception as e:
            print(f"Error ending auction {auction['id']}: {e}")
        
        await log_audit('auction_ended', auction['seller_id'], auction.get('current_bidder'), f"Auction {auction['id']}")
    
    def _create_auction_embed(self, auction: dict, seller: discord.User) -> discord.Embed:
        game = auction['game']
        item = json.loads(auction['item_data']) if isinstance(auction['item_data'], str) else auction['item_data']
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(title=f"Auction: {item['name']}", color=color, timestamp=datetime.utcnow())
        embed.set_author(name=f"Seller: {seller.display_name}", icon_url=seller.display_avatar.url)
        
        if item.get('icon_url'):
            embed.set_thumbnail(url=item['icon_url'])
        
        embed.add_field(name="Game", value=GAME_NAMES.get(game, game.upper()), inline=True)
        embed.add_field(name="Rarity", value=item.get('rarity', 'Unknown'), inline=True)
        embed.add_field(name="Starting Bid", value=f"{auction['starting_bid']:,}", inline=True)
        
        if auction['current_bid'] > 0:
            embed.add_field(name="Current Bid", value=f"{auction['current_bid']:,}", inline=True)
        
        ends = datetime.fromisoformat(auction['ends_at'])
        time_left = ends - datetime.utcnow()
        
        if time_left.total_seconds() > 0:
            hours = int(time_left.total_seconds() // 3600)
            mins = int((time_left.total_seconds() % 3600) // 60)
            embed.add_field(name="Time Left", value=f"{hours}h {mins}m", inline=True)
        else:
            embed.add_field(name="Status", value="Ended", inline=True)
        
        embed.set_footer(text=f"Auction ID: {auction['id'][:30]}")
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(AuctionsCog(bot))
