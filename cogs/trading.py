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
from utils.resolver import item_resolver
from utils.trust_engine import trust_engine, RiskLevel
from utils.validators import Validators
from utils.rate_limit import rate_limiter, action_cooldown
from ui.embeds import TradeEmbed, GAME_NAMES
from ui.views import TradeView, HandoffView, ConfirmView, GameSelectView, DynamicTradeView, DynamicAnnouncementView
from ui.modals import TradeModal

class TradingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    trade_group = app_commands.Group(name="trade", description="Trading commands")
    
    @trade_group.command(name="create", description="Create a new trade offer")
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
        
        modal = TradeModal(game)
        await interaction.response.send_modal(modal)
        
        await modal.wait()
        
        if not modal.trade_data:
            return
        
        offering = modal.trade_data['offering']
        if not offering:
            await interaction.followup.send("You must offer at least one item.", ephemeral=True)
            return
        
        valid, error = Validators.validate_trade_items(offering)
        if not valid:
            await interaction.followup.send(f"Invalid trade: {error}", ephemeral=True)
            return
        
        resolved_items = []
        failed_items = []
        
        for item_name in offering:
            item = await item_resolver.resolve_item(game, item_name)
            if item:
                resolved_items.append(item)
            else:
                suggestions = await item_resolver.suggest_items(game, item_name, limit=3)
                if suggestions:
                    failed_items.append(f"'{item_name}' - Did you mean: {', '.join([s['name'] for s in suggestions])}?")
                else:
                    failed_items.append(f"'{item_name}' - Not found in database")
        
        if failed_items:
            await interaction.followup.send(
                f"Could not resolve some items:\n" + "\n".join(failed_items),
                ephemeral=True
            )
            return
        
        trade_id = await create_trade(
            requester_id=interaction.user.id,
            game=game,
            requester_items=json.dumps([{
                'id': i['id'], 
                'name': i['name'],
                'rarity': i.get('rarity', 'Common'),
                'value': i.get('value', 0),
                'icon_url': i.get('icon_url', '')
            } for i in resolved_items])
        )
        
        if trade_id is None:
            await interaction.followup.send("Failed to create trade.", ephemeral=True)
            return
        
        if target:
            await update_trade(trade_id, target_id=target.id, status='pending')
        
        await add_trade_history(trade_id, 'created', interaction.user.id)
        await log_audit('trade_created', interaction.user.id, target.id if target else None, f"Trade {trade_id}")
        
        trade = await get_trade(trade_id)
        if not trade:
            await interaction.followup.send("Failed to retrieve trade.", ephemeral=True)
            return
        
        requester_user = interaction.user if isinstance(interaction.user, discord.User) else await self.bot.fetch_user(interaction.user.id)
        embed = TradeEmbed.create_trade_offer(trade, requester_user, target)
        
        if target:
            view = DynamicTradeView(trade_id, interaction.user.id, target.id)
            msg = await interaction.followup.send(
                content=f"{target.mention}, you have a trade offer!",
                embed=embed,
                view=view
            )
            
            await interaction.followup.send(
                f"Trade #{trade_id} created and sent to {target.mention}! "
                f"They can accept, decline, or negotiate using the buttons.",
                ephemeral=True
            )
        else:
            if interaction.guild:
                trade_channel_id = await get_game_trade_channel(interaction.guild.id, game)
                if trade_channel_id:
                    trade_channel = interaction.guild.get_channel(trade_channel_id)
                    if trade_channel and isinstance(trade_channel, discord.TextChannel):
                        announcement_view = DynamicAnnouncementView(trade_id, interaction.user.id, game)
                        
                        announcement_embed = discord.Embed(
                            title="New Trade Available!",
                            color=0x2ECC71,
                            description=f"{interaction.user.mention} is looking to trade!"
                        )
                        announcement_embed.add_field(name="Trade ID", value=f"#{trade_id}", inline=True)
                        announcement_embed.add_field(name="Game", value=GAME_NAMES.get(game, game), inline=True)
                        
                        items_str = trade.get('requester_items', '[]')
                        items = json.loads(items_str) if items_str else []
                        if items:
                            items_preview = "\n".join([f"• {i['name']}" for i in items[:5]])
                            if len(items) > 5:
                                items_preview += f"\n... and {len(items) - 5} more items"
                            announcement_embed.add_field(name="Items Offered", value=items_preview, inline=False)
                        
                        user_data = await get_user(interaction.user.id)
                        if user_data:
                            trust_tier = user_data.get('trust_tier', 'Bronze')
                            tier_emoji = {"Bronze": "🥉", "Silver": "🥈", "Gold": "🥇", "Platinum": "💎", "Diamond": "💠"}.get(trust_tier, "🏅")
                            announcement_embed.add_field(
                                name="Trader Info",
                                value=f"Trust: {user_data.get('trust_score', 50):.0f}/100 | {tier_emoji} {trust_tier}",
                                inline=True
                            )
                        
                        announcement_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                        announcement_embed.set_footer(text="Click the buttons below to interact with this trade!")
                        
                        await trade_channel.send(embed=announcement_embed, view=announcement_view)
                        
                        await interaction.followup.send(
                            f"Trade #{trade_id} created and announced in {trade_channel.mention}! "
                            f"Others can express interest using the buttons there.",
                            ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            f"Trade #{trade_id} created! Share it with potential traders or use `/trade view {trade_id}`.",
                            embed=embed
                        )
                else:
                    await interaction.followup.send(
                        f"Trade #{trade_id} created! Share it with potential traders.\n"
                        f"**Tip:** Ask a server admin to set up a trade channel with `/settings tradechannel`",
                        embed=embed
                    )
            else:
                await interaction.followup.send(
                    f"Trade #{trade_id} created! Share it with potential traders.",
                    embed=embed
                )
    
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
