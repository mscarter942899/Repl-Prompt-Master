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
from utils.database_v2 import is_trader_blocked
from utils.resolver import item_resolver
from utils.trust_engine import trust_engine, RiskLevel
from utils.validators import Validators
from utils.rate_limit import rate_limiter, action_cooldown
from ui.embeds import TradeEmbed, GAME_NAMES, GAME_COLORS
from ui.views import TradeView, HandoffView, ConfirmView, GameSelectView, DynamicTradeView, DynamicAnnouncementView
from ui.modals import TradeModal
from ui.trade_builder import TradeBuilderView, format_value, RARITY_EMOJIS

class TradingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    trade_group = app_commands.Group(name="trade", description="Trading commands")
    
    @trade_group.command(name="create", description="Create a new trade offer with visual item builder")
    @app_commands.describe(
        game="The game for this trade",
        target="The user you want to trade with (optional)"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def trade_create(self, interaction: discord.Interaction, game: str, target: Optional[discord.User] = None):
        allowed, retry_after = await rate_limiter.check(interaction.user.id, 'trade_create')
        if not allowed:
            await interaction.response.send_message(
                f"You're creating trades too fast. Please wait {retry_after} seconds.",
                ephemeral=True
            )
            return
        
        user = await get_user(interaction.user.id)
        if not user:
            user = await create_user(interaction.user.id, str(interaction.user.created_at))
        
        if user and user.get('is_banned'):
            await interaction.response.send_message("You are banned from trading.", ephemeral=True)
            return
        
        if target and target.id == interaction.user.id:
            await interaction.response.send_message("You cannot trade with yourself.", ephemeral=True)
            return
        
        if target and target.bot:
            await interaction.response.send_message("You cannot trade with bots.", ephemeral=True)
            return
        
        if target:
            if await is_trader_blocked(target.id, interaction.user.id):
                await interaction.response.send_message("This user has blocked you from trading with them.", ephemeral=True)
                return
            if await is_trader_blocked(interaction.user.id, target.id):
                await interaction.response.send_message("You have blocked this user. Unblock them first to trade.", ephemeral=True)
                return
        
        builder_view = TradeBuilderView(interaction.user.id, game, target.id if target else None)
        embed = builder_view.get_summary_embed()
        
        await interaction.response.send_message(
            embed=embed, 
            view=builder_view, 
            ephemeral=True
        )
        
        try:
            builder_view.message = await interaction.original_response()
        except Exception:
            pass
        
        await builder_view.wait()
        
        if builder_view.cancelled or not builder_view.completed:
            return
        
        trade_data = builder_view.get_trade_data()
        offering_items = trade_data['offering_items']
        requesting_items = trade_data['requesting_items']
        offering_gems = trade_data['offering_gems']
        requesting_gems = trade_data['requesting_gems']
        notes = trade_data['notes']
        
        if not offering_items and offering_gems == 0:
            await interaction.followup.send("You must offer at least one item or some gems.", ephemeral=True)
            return
        
        trade_id = await create_trade(
            requester_id=interaction.user.id,
            game=game,
            requester_items=json.dumps(offering_items),
            target_items=json.dumps(requesting_items) if requesting_items else None
        )
        
        if trade_id is None:
            await interaction.followup.send("Failed to create trade.", ephemeral=True)
            return
        
        update_kwargs = {
            'offering_gems': offering_gems,
            'requesting_gems': requesting_gems
        }
        if notes:
            update_kwargs['notes'] = notes
        if target:
            update_kwargs['target_id'] = target.id
            update_kwargs['status'] = 'pending'
        
        await update_trade(trade_id, **update_kwargs)
        await add_trade_history(trade_id, 'created', interaction.user.id)
        await log_audit('trade_created', interaction.user.id, target.id if target else None, f"Trade {trade_id}")
        
        trade = await get_trade(trade_id)
        if not trade:
            await interaction.followup.send("Failed to retrieve trade.", ephemeral=True)
            return
        
        trade_embed = self._create_enhanced_trade_embed(trade, interaction.user, target)
        
        if target:
            view = DynamicTradeView(trade_id, interaction.user.id, target.id)
            await interaction.followup.send(
                content=f"{target.mention}, you have a trade offer!",
                embed=trade_embed,
                view=view
            )
            
            await interaction.followup.send(
                f"Trade #{trade_id} created and sent to {target.mention}! "
                f"They can accept, decline, counter-offer, or negotiate.",
                ephemeral=True
            )
        else:
            if interaction.guild:
                trade_channel_id = await get_game_trade_channel(interaction.guild.id, game)
                if trade_channel_id:
                    trade_channel = interaction.guild.get_channel(trade_channel_id)
                    if trade_channel and isinstance(trade_channel, discord.TextChannel):
                        announcement_view = DynamicAnnouncementView(trade_id, interaction.user.id, game)
                        
                        announcement_embed = self._create_announcement_embed(
                            trade, interaction.user, game, offering_gems
                        )
                        
                        await trade_channel.send(embed=announcement_embed, view=announcement_view)
                        
                        await interaction.followup.send(
                            f"Trade #{trade_id} created and announced in {trade_channel.mention}!",
                            ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            f"Trade #{trade_id} created! Share it with potential traders.",
                            embed=trade_embed
                        )
                else:
                    await interaction.followup.send(
                        f"Trade #{trade_id} created! Share it with potential traders.\n"
                        f"**Tip:** Ask an admin to set up a trade channel with `/settings tradechannel`",
                        embed=trade_embed
                    )
            else:
                await interaction.followup.send(
                    f"Trade #{trade_id} created! Share it with potential traders.",
                    embed=trade_embed
                )
    
    def _create_enhanced_trade_embed(self, trade: dict, requester: discord.User, 
                                      target: Optional[discord.User] = None) -> discord.Embed:
        game = trade.get('game', 'unknown')
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(
            title=f"Trade Offer #{trade['id']}",
            description=f"**Game:** {GAME_NAMES.get(game, game.upper())}",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_author(name=requester.display_name, icon_url=requester.display_avatar.url)
        
        offering_items = json.loads(trade.get('requester_items', '[]') or '[]')
        offering_gems = trade.get('offering_gems', 0) or 0
        offering_lines = []
        total_offering = 0
        
        for item in offering_items:
            emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
            value = item.get('value', 0)
            total_offering += value
            qty = item.get('quantity', 1)
            line = f"{emoji} **{item['name']}**"
            if qty > 1:
                line += f" x{qty}"
            if value > 0:
                line += f" ({format_value(value)})"
            offering_lines.append(line)
        
        if offering_gems > 0:
            offering_lines.append(f"💎 **{format_value(offering_gems)} Diamonds**")
            total_offering += offering_gems
        
        if offering_lines:
            embed.add_field(
                name=f"📦 Offering",
                value="\n".join(offering_lines[:10]) + (f"\n+{len(offering_lines)-10} more" if len(offering_lines) > 10 else ""),
                inline=True
            )
        
        requesting_items = json.loads(trade.get('target_items', '[]') or '[]')
        requesting_gems = trade.get('requesting_gems', 0) or 0
        requesting_lines = []
        total_requesting = 0
        
        for item in requesting_items:
            emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
            value = item.get('value', 0)
            total_requesting += value
            line = f"{emoji} **{item['name']}**"
            if value > 0:
                line += f" ({format_value(value)})"
            requesting_lines.append(line)
        
        if requesting_gems > 0:
            requesting_lines.append(f"💎 **{format_value(requesting_gems)} Diamonds**")
            total_requesting += requesting_gems
        
        if requesting_lines:
            embed.add_field(
                name=f"🎯 Requesting",
                value="\n".join(requesting_lines[:10]),
                inline=True
            )
        else:
            embed.add_field(name="🎯 Requesting", value="*Open to offers*", inline=True)
        
        if total_offering > 0 or total_requesting > 0:
            diff = total_offering - total_requesting
            if diff > 0:
                analysis = f"📈 Overpay by {format_value(abs(diff))}"
            elif diff < 0:
                analysis = f"📉 Underpay by {format_value(abs(diff))}"
            else:
                analysis = "⚖️ Fair trade"
            embed.add_field(name="💰 Value", value=analysis, inline=True)
        
        notes = trade.get('notes')
        if notes:
            embed.add_field(name="📝 Notes", value=notes[:200], inline=False)
        
        if target:
            embed.add_field(name="📮 To", value=target.mention, inline=True)
        
        status = trade.get('status', 'draft')
        status_emoji = {'draft': '📝', 'pending': '⏳', 'accepted': '✅', 'completed': '🎉', 
                       'cancelled': '❌', 'disputed': '⚠️'}.get(status, '📋')
        embed.set_footer(text=f"{status_emoji} {status.replace('_', ' ').title()}")
        
        return embed
    
    def _create_announcement_embed(self, trade: dict, user: discord.User, 
                                    game: str, offering_gems: int) -> discord.Embed:
        embed = discord.Embed(
            title="🔔 New Trade Available!",
            color=GAME_COLORS.get(game, 0x2ECC71),
            description=f"{user.mention} is looking to trade!"
        )
        embed.add_field(name="Trade ID", value=f"#{trade['id']}", inline=True)
        embed.add_field(name="Game", value=GAME_NAMES.get(game, game), inline=True)
        
        items = json.loads(trade.get('requester_items', '[]') or '[]')
        if items:
            items_preview = []
            for item in items[:5]:
                emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
                items_preview.append(f"{emoji} {item['name']}")
            if len(items) > 5:
                items_preview.append(f"... +{len(items) - 5} more")
            embed.add_field(name="Items Offered", value="\n".join(items_preview), inline=False)
        
        if offering_gems > 0:
            embed.add_field(name="💎 Diamonds", value=format_value(offering_gems), inline=True)
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Click below to make an offer!")
        
        return embed
    
    async def _process_trade_acceptance(self, interaction: discord.Interaction, trade_id: int, target: discord.User):
        trade = await get_trade(trade_id)
        if not trade:
            await interaction.followup.send("Trade not found.", ephemeral=True)
            return
        
        await update_trade(trade_id, status='trust_check')
        await add_trade_history(trade_id, 'accepted', target.id)
        
        requester_data = await get_user(trade['requester_id'])
        target_data = await get_user(target.id)
        
        if not target_data:
            target_data = await create_user(target.id, str(target.created_at))
        
        if not requester_data:
            requester_data = {'trust_score': 50.0, 'total_trades': 0, 'disputed_trades': 0}
        if not target_data:
            target_data = {'trust_score': 50.0, 'total_trades': 0, 'disputed_trades': 0}
        
        requester_items_str = trade.get('requester_items', '[]')
        requester_items = json.loads(requester_items_str) if requester_items_str else []
        
        requester_value = await item_resolver.calculate_trade_value(
            trade['game'], 
            [i['id'] for i in requester_items]
        )
        
        trade_data = {
            'requester_value': requester_value,
            'target_value': 0
        }
        
        risk_level, warnings = trust_engine.assess_trade_risk(
            requester_data, target_data, trade_data
        )
        
        await update_trade(trade_id, risk_level=risk_level.value)
        
        if risk_level == RiskLevel.HIGH_RISK:
            risk_embed = TradeEmbed.create_risk_warning(risk_level, warnings)
            await interaction.followup.send(embed=risk_embed)
            
            view = ConfirmView(target.id)
            confirm_msg = await interaction.followup.send(
                "This trade has been flagged as high risk. Do you still want to proceed?",
                view=view
            )
            
            await view.wait()
            
            if not view.result:
                await update_trade(trade_id, status='cancelled')
                await add_trade_history(trade_id, 'cancelled_risk', target.id)
                await interaction.followup.send("Trade cancelled due to risk concerns.")
                return
        
        await update_trade(trade_id, status='in_game_trade')
        await add_trade_history(trade_id, 'handoff_started', 0)
        
        handoff_embed = TradeEmbed.create_handoff(trade, trade['game'])
        view = HandoffView(trade_id, trade['requester_id'], target.id)
        
        requester = await self.bot.fetch_user(trade['requester_id'])
        
        await interaction.followup.send(
            f"{requester.mention} {target.mention} - Please complete the trade in-game!",
            embed=handoff_embed,
            view=view
        )
        
        await view.wait()
        
        if view.result == 'completed':
            await self._complete_trade(trade_id, trade, requester_data, target_data)
            
            receipt_hash = trust_engine.generate_receipt_hash(trade)
            await update_trade(trade_id, receipt_hash=receipt_hash)
            
            receipt_embed = TradeEmbed.create_receipt(trade, receipt_hash)
            await interaction.followup.send(embed=receipt_embed)
            
        elif view.result == 'disputed':
            await update_trade(trade_id, status='disputed')
            await add_trade_history(trade_id, 'disputed', 0)
            await interaction.followup.send("Trade has been marked as disputed. A moderator will review.")
    
    async def _complete_trade(self, trade_id: int, trade: dict, requester_data: dict, target_data: dict):
        completed_at = datetime.utcnow().isoformat()
        await update_trade(trade_id, status='completed', completed_at=completed_at)
        await add_trade_history(trade_id, 'completed', 0)
        
        req_updates = trust_engine.update_reputation(requester_data, 'trade_completed')
        tgt_updates = trust_engine.update_reputation(target_data, 'trade_completed')
        
        await update_user(trade['requester_id'], **req_updates)
        await update_user(trade['target_id'], **tgt_updates)
        
        await log_audit('trade_completed', trade['requester_id'], trade['target_id'], f"Trade {trade_id}")
    
    @trade_group.command(name="view", description="View a trade by ID")
    @app_commands.describe(trade_id="The trade ID to view")
    async def trade_view(self, interaction: discord.Interaction, trade_id: int):
        trade = await get_trade(trade_id)
        
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        requester = await self.bot.fetch_user(trade['requester_id'])
        target = await self.bot.fetch_user(trade['target_id']) if trade['target_id'] else None
        
        embed = TradeEmbed.create_trade_offer(trade, requester, target)
        await interaction.response.send_message(embed=embed)
    
    @trade_group.command(name="history", description="View your trade history")
    @app_commands.describe(status="Filter by trade status")
    @app_commands.choices(status=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Completed", value="completed"),
        app_commands.Choice(name="Pending", value="pending"),
        app_commands.Choice(name="Disputed", value="disputed")
    ])
    async def trade_history(self, interaction: discord.Interaction, status: str = "all"):
        status_filter = None if status == "all" else status
        trades = await get_user_trades(interaction.user.id, status_filter, limit=10)
        
        if not trades:
            await interaction.response.send_message("No trades found.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Your Trade History",
            color=0x7289DA
        )
        
        for trade in trades:
            game_name = GAME_NAMES.get(trade['game'], trade['game'])
            status_text = trade['status'].replace('_', ' ').title()
            
            embed.add_field(
                name=f"Trade #{trade['id']} - {game_name}",
                value=f"Status: {status_text}\nCreated: {trade['created_at'][:10]}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)
    
    @trade_group.command(name="verify", description="Verify a trade receipt by hash")
    @app_commands.describe(receipt_hash="The receipt hash to verify")
    async def trade_verify(self, interaction: discord.Interaction, receipt_hash: str):
        from utils.database import get_db
        import aiosqlite
        
        async with aiosqlite.connect("data/trading_bot.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM trades WHERE receipt_hash LIKE ?",
                (f"{receipt_hash}%",)
            ) as cursor:
                trade = await cursor.fetchone()
        
        if not trade:
            await interaction.response.send_message(
                "No trade found with that receipt hash.",
                ephemeral=True
            )
            return
        
        trade = dict(trade)
        
        is_valid = trust_engine.verify_receipt(trade, trade.get('receipt_hash', ''))
        
        embed = discord.Embed(
            title="Trade Receipt Verification",
            color=0x2ECC71 if is_valid else 0xE74C3C,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Trade ID", value=str(trade['id']), inline=True)
        embed.add_field(name="Status", value=trade['status'].replace('_', ' ').title(), inline=True)
        embed.add_field(name="Game", value=GAME_NAMES.get(trade['game'], trade['game'].upper()), inline=True)
        
        embed.add_field(
            name="Verification",
            value="✅ Valid - Receipt hash matches" if is_valid else "❌ Invalid - Receipt may have been tampered",
            inline=False
        )
        
        if trade.get('completed_at'):
            embed.add_field(name="Completed", value=trade['completed_at'][:19], inline=True)
        
        embed.add_field(
            name="Receipt Hash",
            value=f"`{trade.get('receipt_hash', 'N/A')[:32]}...`",
            inline=False
        )
        
        embed.set_footer(text="This receipt is immutable and cryptographically verified")
        
        await interaction.response.send_message(embed=embed)
    
    @trade_group.command(name="cancel", description="Cancel a pending trade")
    @app_commands.describe(trade_id="The trade ID to cancel")
    async def trade_cancel(self, interaction: discord.Interaction, trade_id: int):
        trade = await get_trade(trade_id)
        
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        if trade['requester_id'] != interaction.user.id:
            await interaction.response.send_message("You can only cancel your own trades.", ephemeral=True)
            return
        
        if trade['status'] not in ('draft', 'pending'):
            await interaction.response.send_message("This trade cannot be cancelled.", ephemeral=True)
            return
        
        await update_trade(trade_id, status='cancelled')
        await add_trade_history(trade_id, 'cancelled', interaction.user.id)
        
        user = await get_user(interaction.user.id)
        if user:
            updates = trust_engine.update_reputation(user, 'trade_cancelled')
            await update_user(interaction.user.id, **updates)
        
        await interaction.response.send_message(f"Trade #{trade_id} has been cancelled.")


async def setup(bot: commands.Bot):
    await bot.add_cog(TradingCog(bot))
