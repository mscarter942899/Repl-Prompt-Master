import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json
from datetime import datetime, timedelta

from utils.database import (
    get_user, create_user, update_user, 
    create_trade, update_trade, get_trade, get_user_trades,
    add_trade_history, log_audit, get_trade_channel, get_game_trade_channel
)
from utils.database_v2 import (
    init_enhanced_tables, add_to_wishlist, remove_from_wishlist, get_wishlist,
    create_lf_ft_post, get_active_lf_ft_posts, add_trader_review, get_trader_reviews,
    get_trader_rating_summary, add_favorite_trader, remove_favorite_trader,
    get_favorite_traders, block_trader, unblock_trader, is_trader_blocked,
    get_blocked_traders, save_trade_template, get_trade_templates, delete_trade_template,
    set_trade_feed_settings, get_trade_feed_settings, get_trade_leaderboard,
    check_wishlist_matches
)
from utils.resolver import item_resolver
from utils.trust_engine import trust_engine
from utils.rate_limit import rate_limiter
from ui.embeds import GAME_NAMES, GAME_COLORS
from ui.trade_builder import TradeBuilderView, format_value, RARITY_EMOJIS
from ui.enhanced_embeds import EnhancedTradeEmbed, WishlistEmbed, LeaderboardEmbed, LFFTEmbed
from ui.views import DynamicTradeView, DynamicAnnouncementView


class EnhancedTradingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self._init_tables())
    
    async def _init_tables(self):
        await init_enhanced_tables()
    
    wishlist_group = app_commands.Group(name="wishlist", description="Wishlist commands")
    
    @wishlist_group.command(name="add", description="Add an item to your wishlist")
    @app_commands.describe(
        game="The game for this item",
        item="The item you're looking for",
        priority="Priority level (1-3, higher = more wanted)",
        max_price="Maximum price you'd pay (optional)"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def wishlist_add(self, interaction: discord.Interaction, game: str, item: str, 
                           priority: int = 1, max_price: Optional[str] = None):
        resolved = await item_resolver.resolve_item(game, item)
        
        if not resolved:
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
        
        max_price_val = None
        if max_price:
            from ui.trade_builder import parse_gem_value
            max_price_val = parse_gem_value(max_price)
        
        priority = max(1, min(3, priority))
        
        success = await add_to_wishlist(
            interaction.user.id, game, resolved['id'], resolved['name'],
            priority, max_price_val
        )
        
        if success:
            emoji = RARITY_EMOJIS.get(resolved.get('rarity', 'Common'), '⚪')
            embed = discord.Embed(
                title="✅ Added to Wishlist",
                description=f"{emoji} **{resolved['name']}** added to your {GAME_NAMES.get(game, game)} wishlist!",
                color=0x2ECC71
            )
            if max_price_val:
                embed.add_field(name="Max Price", value=format_value(max_price_val))
            embed.add_field(name="Priority", value="🔥" * priority)
            
            if resolved.get('icon_url'):
                embed.set_thumbnail(url=resolved['icon_url'])
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Failed to add item to wishlist.", ephemeral=True)
    
    @wishlist_group.command(name="view", description="View your wishlist")
    @app_commands.describe(game="Filter by game (optional)")
    @app_commands.choices(game=[
        app_commands.Choice(name="All Games", value="all"),
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def wishlist_view(self, interaction: discord.Interaction, game: str = "all"):
        game_filter = None if game == "all" else game
        items = await get_wishlist(interaction.user.id, game_filter)
        
        if not items:
            await interaction.response.send_message("Your wishlist is empty!", ephemeral=True)
            return
        
        if game_filter:
            embed = WishlistEmbed.create(interaction.user, items, game_filter)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            games_items = {}
            for item in items:
                g = item.get('game', 'unknown')
                if g not in games_items:
                    games_items[g] = []
                games_items[g].append(item)
            
            embeds = [WishlistEmbed.create(interaction.user, g_items, g) for g, g_items in games_items.items()]
            await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)
    
    @wishlist_group.command(name="remove", description="Remove an item from your wishlist")
    @app_commands.describe(game="The game", item="The item to remove")
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def wishlist_remove(self, interaction: discord.Interaction, game: str, item: str):
        resolved = await item_resolver.resolve_item(game, item)
        item_id = resolved['id'] if resolved else item.lower().replace(' ', '_')
        
        success = await remove_from_wishlist(interaction.user.id, game, item_id)
        
        if success:
            await interaction.response.send_message("✅ Item removed from wishlist!", ephemeral=True)
        else:
            await interaction.response.send_message("Item not found in your wishlist.", ephemeral=True)
    
    trader_group = app_commands.Group(name="trader", description="Trader management commands")
    
    @trader_group.command(name="favorite", description="Add a trader to your favorites")
    @app_commands.describe(user="The trader to favorite")
    async def trader_favorite(self, interaction: discord.Interaction, user: discord.User):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You can't favorite yourself!", ephemeral=True)
            return
        
        if user.bot:
            await interaction.response.send_message("You can't favorite bots!", ephemeral=True)
            return
        
        success = await add_favorite_trader(interaction.user.id, user.id)
        
        if success:
            embed = discord.Embed(
                title="⭐ Trader Favorited",
                description=f"Added {user.mention} to your favorite traders!",
                color=0xFFD700
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("This trader is already in your favorites!", ephemeral=True)
    
    @trader_group.command(name="unfavorite", description="Remove a trader from favorites")
    @app_commands.describe(user="The trader to remove")
    async def trader_unfavorite(self, interaction: discord.Interaction, user: discord.User):
        success = await remove_favorite_trader(interaction.user.id, user.id)
        if success:
            await interaction.response.send_message(f"Removed {user.display_name} from favorites.", ephemeral=True)
        else:
            await interaction.response.send_message("Trader not in your favorites.", ephemeral=True)
    
    @trader_group.command(name="favorites", description="View your favorite traders")
    async def trader_favorites(self, interaction: discord.Interaction):
        favorites = await get_favorite_traders(interaction.user.id)
        
        if not favorites:
            await interaction.response.send_message("You haven't favorited any traders yet!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⭐ Your Favorite Traders",
            color=0xFFD700
        )
        
        lines = []
        for fav in favorites[:20]:
            try:
                user = await self.bot.fetch_user(fav['favorite_id'])
                lines.append(f"• {user.mention}")
            except:
                lines.append(f"• Unknown User ({fav['favorite_id']})")
        
        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @trader_group.command(name="block", description="Block a trader from trading with you")
    @app_commands.describe(user="The trader to block", reason="Reason for blocking")
    async def trader_block(self, interaction: discord.Interaction, user: discord.User, reason: Optional[str] = None):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You can't block yourself!", ephemeral=True)
            return
        
        success = await block_trader(interaction.user.id, user.id, reason)
        
        if success:
            await interaction.response.send_message(
                f"🚫 Blocked {user.display_name}. They can no longer trade with you.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("This trader is already blocked!", ephemeral=True)
    
    @trader_group.command(name="unblock", description="Unblock a trader")
    @app_commands.describe(user="The trader to unblock")
    async def trader_unblock(self, interaction: discord.Interaction, user: discord.User):
        success = await unblock_trader(interaction.user.id, user.id)
        if success:
            await interaction.response.send_message(f"✅ Unblocked {user.display_name}.", ephemeral=True)
        else:
            await interaction.response.send_message("Trader not in your block list.", ephemeral=True)
    
    @trader_group.command(name="review", description="Leave a review for a trader")
    @app_commands.describe(
        user="The trader to review",
        trade_id="The trade ID this review is for",
        rating="Rating from 1-5 stars",
        comment="Your review comment"
    )
    async def trader_review(self, interaction: discord.Interaction, user: discord.User, 
                            trade_id: int, rating: int, comment: Optional[str] = None):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You can't review yourself!", ephemeral=True)
            return
        
        rating = max(1, min(5, rating))
        
        trade = await get_trade(trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        if interaction.user.id not in (trade['requester_id'], trade['target_id']):
            await interaction.response.send_message("You weren't part of this trade.", ephemeral=True)
            return
        
        if trade['status'] != 'completed':
            await interaction.response.send_message("You can only review completed trades.", ephemeral=True)
            return
        
        success = await add_trader_review(interaction.user.id, user.id, trade_id, rating, comment)
        
        if success:
            stars = "⭐" * rating
            embed = discord.Embed(
                title="✅ Review Submitted",
                description=f"You gave {user.mention} {stars}",
                color=0x2ECC71
            )
            if comment:
                embed.add_field(name="Comment", value=comment[:200])
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("You've already reviewed this trade!", ephemeral=True)
    
    @trader_group.command(name="reviews", description="View a trader's reviews")
    @app_commands.describe(user="The trader to view reviews for")
    async def trader_reviews(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        target = user or interaction.user
        
        summary = await get_trader_rating_summary(target.id)
        reviews = await get_trader_reviews(target.id, limit=5)
        
        embed = discord.Embed(
            title=f"📊 {target.display_name}'s Reviews",
            color=0x3498DB
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        if summary['total'] > 0:
            avg_stars = "⭐" * round(summary['average'])
            embed.add_field(
                name="Overall Rating",
                value=f"{avg_stars} ({summary['average']:.1f}/5)",
                inline=True
            )
            embed.add_field(
                name="Total Reviews",
                value=str(summary['total']),
                inline=True
            )
            embed.add_field(
                name="Breakdown",
                value=f"👍 {summary['positive']} | 😐 {summary['neutral']} | 👎 {summary['negative']}",
                inline=True
            )
            
            if reviews:
                review_text = []
                for r in reviews:
                    stars = "⭐" * r['rating']
                    text = f"{stars}"
                    if r.get('review_text'):
                        text += f" - *{r['review_text'][:50]}*"
                    review_text.append(text)
                embed.add_field(name="Recent Reviews", value="\n".join(review_text), inline=False)
        else:
            embed.description = "No reviews yet!"
        
        await interaction.response.send_message(embed=embed)
    
    leaderboard_group = app_commands.Group(name="leaderboard", description="Trading leaderboards")
    
    @leaderboard_group.command(name="trades", description="View top traders by trade count")
    async def leaderboard_trades(self, interaction: discord.Interaction):
        leaders = await get_trade_leaderboard(metric='total_trades')
        embed = LeaderboardEmbed.create(self.bot, leaders, 'total_trades')
        await interaction.response.send_message(embed=embed)
    
    @leaderboard_group.command(name="trust", description="View traders with highest trust scores")
    async def leaderboard_trust(self, interaction: discord.Interaction):
        leaders = await get_trade_leaderboard(metric='trust_score')
        embed = LeaderboardEmbed.create(self.bot, leaders, 'trust_score')
        await interaction.response.send_message(embed=embed)
    
    @leaderboard_group.command(name="value", description="View top traders by total value traded")
    async def leaderboard_value(self, interaction: discord.Interaction):
        leaders = await get_trade_leaderboard(metric='total_value_traded')
        embed = LeaderboardEmbed.create(self.bot, leaders, 'total_value_traded')
        await interaction.response.send_message(embed=embed)
    
    post_group = app_commands.Group(name="post", description="LF/FT posting commands")
    
    @post_group.command(name="lf", description="Post items you're Looking For")
    @app_commands.describe(
        game="The game",
        items="Items you're looking for (comma separated)",
        gems="Gems you're offering (PS99 only)",
        notes="Additional notes"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def post_lf(self, interaction: discord.Interaction, game: str, items: str,
                      gems: Optional[str] = None, notes: Optional[str] = None):
        if not interaction.guild:
            await interaction.response.send_message("This command only works in servers.", ephemeral=True)
            return
        
        item_list = [i.strip() for i in items.split(',') if i.strip()]
        
        resolved_items = []
        for item_name in item_list:
            resolved = await item_resolver.resolve_item(game, item_name)
            if resolved:
                resolved_items.append({
                    'id': resolved['id'],
                    'name': resolved['name'],
                    'rarity': resolved.get('rarity', 'Unknown'),
                    'value': resolved.get('value', 0)
                })
            else:
                resolved_items.append({'name': item_name, 'rarity': 'Unknown', 'value': 0})
        
        gem_amount = 0
        if gems and game == 'ps99':
            from ui.trade_builder import parse_gem_value
            gem_amount = parse_gem_value(gems)
        
        post_id = await create_lf_ft_post(
            interaction.user.id, interaction.guild.id, game, 'lf',
            resolved_items, gem_amount, notes
        )
        
        if post_id:
            post = {
                'id': post_id,
                'game': game,
                'post_type': 'lf',
                'items': resolved_items,
                'gems': gem_amount,
                'notes': notes
            }
            embed = LFFTEmbed.create_post(post, interaction.user)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Failed to create post.", ephemeral=True)
    
    @post_group.command(name="ft", description="Post items you have For Trade")
    @app_commands.describe(
        game="The game",
        items="Items you're trading (comma separated)",
        gems="Gems you're including (PS99 only)",
        notes="Additional notes"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def post_ft(self, interaction: discord.Interaction, game: str, items: str,
                      gems: Optional[str] = None, notes: Optional[str] = None):
        if not interaction.guild:
            await interaction.response.send_message("This command only works in servers.", ephemeral=True)
            return
        
        item_list = [i.strip() for i in items.split(',') if i.strip()]
        
        resolved_items = []
        for item_name in item_list:
            resolved = await item_resolver.resolve_item(game, item_name)
            if resolved:
                resolved_items.append({
                    'id': resolved['id'],
                    'name': resolved['name'],
                    'rarity': resolved.get('rarity', 'Unknown'),
                    'value': resolved.get('value', 0),
                    'icon_url': resolved.get('icon_url', '')
                })
            else:
                resolved_items.append({'name': item_name, 'rarity': 'Unknown', 'value': 0})
        
        gem_amount = 0
        if gems and game == 'ps99':
            from ui.trade_builder import parse_gem_value
            gem_amount = parse_gem_value(gems)
        
        post_id = await create_lf_ft_post(
            interaction.user.id, interaction.guild.id, game, 'ft',
            resolved_items, gem_amount, notes
        )
        
        if post_id:
            wishlist_matches = await check_wishlist_matches(game, resolved_items)
            
            post = {
                'id': post_id,
                'game': game,
                'post_type': 'ft',
                'items': resolved_items,
                'gems': gem_amount,
                'notes': notes
            }
            embed = LFFTEmbed.create_post(post, interaction.user)
            
            if wishlist_matches:
                match_text = f"📢 {len(wishlist_matches)} users have items you're offering on their wishlist!"
                embed.add_field(name="Wishlist Matches", value=match_text, inline=False)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Failed to create post.", ephemeral=True)
    
    @post_group.command(name="browse", description="Browse LF/FT posts")
    @app_commands.describe(
        game="Filter by game",
        post_type="Filter by type"
    )
    @app_commands.choices(
        game=[
            app_commands.Choice(name="All Games", value="all"),
            app_commands.Choice(name="Pet Simulator 99", value="ps99"),
            app_commands.Choice(name="Grow a Garden", value="gag"),
            app_commands.Choice(name="Adopt Me", value="am"),
            app_commands.Choice(name="Blox Fruits", value="bf"),
            app_commands.Choice(name="Steal a Brainrot", value="sab")
        ],
        post_type=[
            app_commands.Choice(name="All", value="all"),
            app_commands.Choice(name="Looking For", value="lf"),
            app_commands.Choice(name="For Trade", value="ft")
        ]
    )
    async def post_browse(self, interaction: discord.Interaction, 
                          game: str = "all", post_type: str = "all"):
        if not interaction.guild:
            await interaction.response.send_message("This command only works in servers.", ephemeral=True)
            return
        
        game_filter = None if game == "all" else game
        type_filter = None if post_type == "all" else post_type
        
        posts = await get_active_lf_ft_posts(interaction.guild.id, game_filter, type_filter, limit=10)
        
        if not posts:
            await interaction.response.send_message("No active posts found!", ephemeral=True)
            return
        
        embeds = []
        for post in posts[:5]:
            try:
                user = await self.bot.fetch_user(post['user_id'])
                embed = LFFTEmbed.create_post(post, user)
                embeds.append(embed)
            except:
                continue
        
        if embeds:
            await interaction.response.send_message(embeds=embeds)
        else:
            await interaction.response.send_message("No posts to display.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EnhancedTradingCog(bot))
