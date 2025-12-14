import discord
from discord.ui import View, Button
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger('RobloxTradingBot')

GAME_NAMES = {
    'ps99': 'Pet Simulator 99',
    'gag': 'Grow a Garden',
    'am': 'Adopt Me',
    'bf': 'Blox Fruits',
    'sab': 'Steal a Brainrot'
}

GAME_EMOJIS = {
    'ps99': '🐾',
    'gag': '🌱',
    'am': '🏠',
    'bf': '🍎',
    'sab': '🧠'
}

GAME_COLORS = {
    'ps99': 0x9B59B6,
    'gag': 0x2ECC71,
    'am': 0xE74C3C,
    'bf': 0x3498DB,
    'sab': 0xF39C12
}

TIER_EMOJIS = {
    "Bronze": "🥉",
    "Silver": "🥈", 
    "Gold": "🥇",
    "Platinum": "💎",
    "Diamond": "💠"
}


async def safe_fetch_trade(trade_id: int) -> Optional[Dict]:
    try:
        from utils.database import get_trade
        return await get_trade(trade_id)
    except Exception as e:
        logger.error(f"Error fetching trade {trade_id}: {e}")
        return None


async def safe_fetch_user(client, user_id: int):
    try:
        return await client.fetch_user(user_id)
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return None


def create_success_embed(title: str, description: str, game: Optional[str] = None) -> discord.Embed:
    color = GAME_COLORS.get(game, 0x2ECC71) if game else 0x2ECC71
    embed = discord.Embed(title=f"✅ {title}", description=description, color=color)
    if game:
        embed.set_footer(text=f"{GAME_EMOJIS.get(game, '🎮')} {GAME_NAMES.get(game, game)}")
    return embed


def create_error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=description, color=0xE74C3C)


def create_info_embed(title: str, description: str, game: Optional[str] = None) -> discord.Embed:
    color = GAME_COLORS.get(game, 0x3498DB) if game else 0x3498DB
    embed = discord.Embed(title=f"ℹ️ {title}", description=description, color=color)
    if game:
        embed.set_footer(text=f"{GAME_EMOJIS.get(game, '🎮')} {GAME_NAMES.get(game, game)}")
    return embed




async def disable_message_buttons(interaction: discord.Interaction):
    if interaction.message:
        try:
            disabled_view = View(timeout=None)
            for action_row in interaction.message.components:
                children = getattr(action_row, 'children', [])
                for child in children:
                    if hasattr(child, 'custom_id') and hasattr(child, 'label'):
                        btn = Button(
                            label=getattr(child, 'label', 'Button') or 'Button',
                            style=getattr(child, 'style', discord.ButtonStyle.secondary),
                            custom_id=getattr(child, 'custom_id', ''),
                            disabled=True,
                            emoji=getattr(child, 'emoji', None),
                        )
                        disabled_view.add_item(btn)
            if disabled_view.children:
                await interaction.message.edit(view=disabled_view)
        except Exception as e:
            logger.error(f"Error disabling buttons: {e}")


async def handle_trade_accept(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history, create_trade_ticket
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists or has been deleted.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id != trade['target_id']:
        embed = create_error_embed("Access Denied", "Only the trade recipient can accept this offer.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if trade['status'] not in ('pending', 'draft'):
        embed = create_error_embed("Invalid Status", f"This trade is already {trade['status']}.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    try:
        await update_trade(trade_id, status='accepted')
        await add_trade_history(trade_id, 'accepted', interaction.user.id)
    except Exception as e:
        logger.error(f"Error accepting trade: {e}")
        embed = create_error_embed("Error", "Failed to accept trade. Please try again.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    await disable_message_buttons(interaction)
    
    game = trade['game']
    game_name = GAME_NAMES.get(game, game)
    game_emoji = GAME_EMOJIS.get(game, '🎮')
    game_color = GAME_COLORS.get(game, 0x2ECC71)
    
    requester = await safe_fetch_user(interaction.client, trade['requester_id'])
    requester_mention = requester.mention if requester else f"<@{trade['requester_id']}>"
    
    if interaction.guild and interaction.channel and isinstance(interaction.channel, discord.TextChannel):
        try:
            thread = await interaction.channel.create_thread(
                name=f"🎫 Trade #{trade_id} - {requester.display_name if requester else 'Trader'} & {interaction.user.display_name}",
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440
            )
            
            try:
                if requester:
                    await thread.add_user(requester)
                await thread.add_user(interaction.user)
            except (discord.Forbidden, discord.HTTPException):
                pass
            
            await create_trade_ticket(
                trade_id=trade_id,
                thread_id=thread.id,
                channel_id=interaction.channel.id,
                guild_id=interaction.guild.id,
                requester_id=trade['requester_id'],
                target_id=trade['target_id']
            )
            
            welcome_embed = discord.Embed(
                title=f"🎫 Trade Ticket #{trade_id}",
                description=f"{game_emoji} **{game_name}** trade between {requester_mention} and {interaction.user.mention}",
                color=game_color
            )
            welcome_embed.add_field(
                name="📋 How to Complete Your Trade",
                value="1️⃣ Share your Roblox usernames using the button below\n"
                      "2️⃣ Add each other as friends in Roblox\n"
                      "3️⃣ Meet up and complete the trade in-game\n"
                      "4️⃣ Both confirm using the green button when done",
                inline=False
            )
            welcome_embed.add_field(
                name="⚠️ Stay Safe",
                value="• Verify items before accepting in-game\n"
                      "• Take screenshots as proof\n"
                      "• Report any issues immediately",
                inline=False
            )
            welcome_embed.set_footer(text="This ticket auto-archives after 24 hours of inactivity")
            
            from ui.views import TradeTicketView
            ticket_view = TradeTicketView(trade_id, trade['requester_id'], trade['target_id'], game)
            
            await thread.send(
                f"🔔 {requester_mention} {interaction.user.mention}",
                embed=welcome_embed,
                view=ticket_view
            )
            
            success_embed = discord.Embed(
                title="✅ Trade Accepted!",
                description=f"A private trade ticket has been created for Trade #{trade_id}.",
                color=game_color
            )
            success_embed.add_field(name="Trade Room", value=thread.mention, inline=True)
            success_embed.add_field(name="Game", value=f"{game_emoji} {game_name}", inline=True)
            
            await interaction.response.send_message(embed=success_embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="✅ Trade Accepted!",
                description="I couldn't create a private thread. Please coordinate in DMs.",
                color=game_color
            )
            await interaction.response.send_message(embed=embed)
            
            from ui.views import DynamicHandoffView
            handoff_view = DynamicHandoffView(trade_id, trade['requester_id'], trade['target_id'])
            await interaction.followup.send(
                f"{requester_mention} {interaction.user.mention} - Complete your {game_emoji} {game_name} trade!",
                view=handoff_view
            )
    else:
        embed = discord.Embed(
            title="✅ Trade Accepted!",
            description="Complete the trade in-game and confirm below when done.",
            color=game_color
        )
        await interaction.response.send_message(embed=embed)
        
        from ui.views import DynamicHandoffView
        handoff_view = DynamicHandoffView(trade_id, trade['requester_id'], trade['target_id'])
        await interaction.followup.send(
            f"{requester_mention} {interaction.user.mention} - Complete your trade!",
            view=handoff_view
        )


async def handle_trade_decline(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        embed = create_error_embed("Access Denied", "You are not part of this trade.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    try:
        await update_trade(trade_id, status='cancelled')
        await add_trade_history(trade_id, 'declined', interaction.user.id)
    except Exception as e:
        logger.error(f"Error declining trade: {e}")
        embed = create_error_embed("Error", "Failed to decline trade.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    await disable_message_buttons(interaction)
    
    embed = discord.Embed(
        title="❌ Trade Declined",
        description=f"Trade #{trade_id} has been cancelled by {interaction.user.display_name}.",
        color=0xE74C3C
    )
    embed.set_footer(text="You can create a new trade anytime with /trade create")
    await interaction.response.send_message(embed=embed)


async def handle_trade_counter(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id != trade['target_id']:
        embed = create_error_embed("Access Denied", "Only the trade recipient can make a counter offer.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    from ui.views import CounterOfferModal
    modal = CounterOfferModal(trade_id, trade['game'], trade['requester_id'])
    await interaction.response.send_modal(modal)


async def handle_trade_negotiate(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.views import NegotiateModal
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        embed = create_error_embed("Access Denied", "You are not part of this trade.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    modal = NegotiateModal(trade_id)
    await interaction.response.send_modal(modal)


async def handle_trade_details(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.trade_builder import format_value, RARITY_EMOJIS
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    game = trade['game']
    game_name = GAME_NAMES.get(game, game)
    game_emoji = GAME_EMOJIS.get(game, '🎮')
    game_color = GAME_COLORS.get(game, 0x3498DB)
    
    items_str = trade.get('requester_items', '[]')
    items = json.loads(items_str) if items_str else []
    
    status_emoji = {
        'pending': '⏳',
        'accepted': '✅',
        'completed': '🎉',
        'cancelled': '❌',
        'disputed': '⚠️'
    }.get(trade['status'], '❓')
    
    risk_emoji = {
        'low': '🟢',
        'medium': '🟡',
        'high': '🟠',
        'critical': '🔴'
    }.get(trade.get('risk_level', 'unknown'), '⚪')
    
    embed = discord.Embed(
        title=f"📋 Trade #{trade_id} Details",
        color=game_color
    )
    embed.add_field(name="Game", value=f"{game_emoji} {game_name}", inline=True)
    embed.add_field(name="Status", value=f"{status_emoji} {trade['status'].replace('_', ' ').title()}", inline=True)
    embed.add_field(name="Risk", value=f"{risk_emoji} {trade.get('risk_level', 'Unknown').title()}", inline=True)
    
    if items:
        items_list = []
        for i in items[:8]:
            emoji = RARITY_EMOJIS.get(i.get('rarity', 'Common'), '⚪')
            qty = i.get('quantity', 1)
            name = i['name']
            if qty > 1:
                name += f" x{qty}"
            items_list.append(f"{emoji} {name}")
        
        items_text = "\n".join(items_list)
        if len(items) > 8:
            items_text += f"\n*+{len(items) - 8} more items*"
        embed.add_field(name="📦 Items Offered", value=items_text, inline=False)
    
    total_value = sum(i.get('value', 0) * i.get('quantity', 1) for i in items)
    embed.add_field(name="💰 Total Value", value=format_value(total_value), inline=True)
    
    if items and items[0].get('icon_url'):
        embed.set_thumbnail(url=items[0]['icon_url'])
    
    embed.set_footer(text=f"Trade #{trade_id} • Created {trade.get('created_at', 'Unknown')[:10]}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_trade_profile(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, get_user
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    other_id = trade['target_id'] if interaction.user.id == trade['requester_id'] else trade['requester_id']
    other_user = await safe_fetch_user(interaction.client, other_id)
    user_data = await get_user(other_id)
    
    embed = discord.Embed(
        title=f"👤 {other_user.display_name if other_user else 'Unknown User'}'s Profile",
        color=0x9B59B6
    )
    
    if other_user:
        embed.set_thumbnail(url=other_user.display_avatar.url)
    
    if user_data:
        trust_tier = user_data.get('trust_tier', 'Bronze')
        tier_emoji = TIER_EMOJIS.get(trust_tier, "🏅")
        trust_score = user_data.get('trust_score', 50)
        
        trust_bar = "█" * int(trust_score / 10) + "░" * (10 - int(trust_score / 10))
        
        embed.add_field(
            name="🏆 Trust Rating",
            value=f"{tier_emoji} **{trust_tier}**\n`[{trust_bar}]` {trust_score:.1f}/100",
            inline=False
        )
        
        total = user_data.get('total_trades', 0)
        success = user_data.get('successful_trades', 0)
        disputed = user_data.get('disputed_trades', 0)
        success_rate = (success / total * 100) if total > 0 else 0
        
        embed.add_field(name="📊 Total Trades", value=str(total), inline=True)
        embed.add_field(name="✅ Successful", value=f"{success} ({success_rate:.0f}%)", inline=True)
        embed.add_field(name="⚠️ Disputed", value=str(disputed), inline=True)
        
        if user_data.get('roblox_username'):
            embed.add_field(name="🎮 Roblox", value=user_data['roblox_username'], inline=True)
    else:
        embed.description = "This user hasn't completed any trades yet. They're new to trading!"
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_trade_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Trading Guide",
        description="Welcome to the Roblox Trading Bot! Here's how everything works:",
        color=0x3498DB
    )
    
    embed.add_field(
        name="1️⃣ Accept or Decline",
        value="Review the offer and choose to accept or pass.",
        inline=False
    )
    embed.add_field(
        name="2️⃣ Counter Offer",
        value="Not quite right? Make a counter offer with your terms.",
        inline=False
    )
    embed.add_field(
        name="3️⃣ Negotiate",
        value="Send a message to discuss the trade details.",
        inline=False
    )
    embed.add_field(
        name="4️⃣ Complete In-Game",
        value="Once accepted, meet in Roblox and complete the trade.",
        inline=False
    )
    embed.add_field(
        name="5️⃣ Confirm",
        value="Both traders confirm when done to build trust scores!",
        inline=False
    )
    
    embed.set_footer(text="Stay safe and happy trading! 🎮")
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_handoff_confirm(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history, get_user, update_user
    from utils.trust_engine import trust_engine
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    requester_id = trade['requester_id']
    target_id = trade['target_id']
    
    if interaction.user.id not in (requester_id, target_id):
        embed = create_error_embed("Access Denied", "You are not part of this trade.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    try:
        field = 'requester_confirmed' if interaction.user.id == requester_id else 'target_confirmed'
        await update_trade(trade_id, **{field: 1})
        
        trade = await safe_fetch_trade(trade_id)
        if trade and trade['requester_confirmed'] and trade['target_confirmed']:
            await update_trade(trade_id, status='completed', completed_at=datetime.utcnow().isoformat())
            await add_trade_history(trade_id, 'completed', 0)
            
            requester_data = await get_user(requester_id)
            target_data = await get_user(target_id)
            
            if requester_data:
                req_updates = trust_engine.update_reputation(requester_data, 'trade_completed')
                await update_user(requester_id, **req_updates)
            if target_data:
                tgt_updates = trust_engine.update_reputation(target_data, 'trade_completed')
                await update_user(target_id, **tgt_updates)
            
            await disable_message_buttons(interaction)
            
            receipt_hash = trust_engine.generate_receipt_hash(trade)
            await update_trade(trade_id, receipt_hash=receipt_hash)
            
            game = trade['game']
            game_emoji = GAME_EMOJIS.get(game, '🎮')
            game_color = GAME_COLORS.get(game, 0x2ECC71)
            
            embed = discord.Embed(
                title="🎉 Trade Completed Successfully!",
                description=f"Trade #{trade_id} has been verified and completed.",
                color=game_color
            )
            embed.add_field(name="📜 Receipt", value=f"`{receipt_hash[:24]}...`", inline=False)
            embed.add_field(name="🏆 Rewards", value="Both traders earned trust points!", inline=True)
            embed.set_footer(text=f"{game_emoji} Keep trading to level up your trust tier!")
            
            await interaction.response.send_message(embed=embed)
        else:
            other_id = target_id if interaction.user.id == requester_id else requester_id
            other_user = await safe_fetch_user(interaction.client, other_id)
            
            embed = discord.Embed(
                title="✅ Confirmation Received!",
                description=f"Waiting for {other_user.display_name if other_user else 'the other trader'} to confirm...",
                color=0xF1C40F
            )
            embed.set_footer(text="The trade will complete when both parties confirm.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
    except Exception as e:
        logger.error(f"Error confirming trade: {e}")
        embed = create_error_embed("Error", "Failed to confirm trade. Please try again.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_handoff_issue(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        embed = create_error_embed("Access Denied", "You are not part of this trade.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    try:
        await update_trade(trade_id, status='disputed')
        await add_trade_history(trade_id, 'disputed', interaction.user.id)
    except Exception as e:
        logger.error(f"Error disputing trade: {e}")
    
    await disable_message_buttons(interaction)
    
    embed = discord.Embed(
        title="⚠️ Trade Dispute Filed",
        description=f"Trade #{trade_id} has been flagged for moderator review.",
        color=0xE74C3C
    )
    embed.add_field(name="Reported By", value=interaction.user.mention, inline=True)
    embed.add_field(name="Status", value="Awaiting Review", inline=True)
    embed.add_field(
        name="What Happens Next?",
        value="• A moderator will review this trade\n"
              "• Please provide any evidence you have\n"
              "• Do not delete any messages",
        inline=False
    )
    embed.set_footer(text="Keep screenshots of the in-game trade as evidence")
    
    await interaction.response.send_message(embed=embed)


async def handle_handoff_proof(interaction: discord.Interaction, trade_id: int):
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        embed = create_error_embed("Access Denied", "You are not part of this trade.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    embed = discord.Embed(
        title="📸 Upload Trade Proof",
        description="To upload proof of your completed trade:",
        color=0x3498DB
    )
    embed.add_field(
        name="Instructions",
        value="1. Take a screenshot of the completed in-game trade\n"
              "2. Reply to this message with your screenshot attached\n"
              "3. The image will be saved as proof for Trade #" + str(trade_id),
        inline=False
    )
    embed.set_footer(text="Screenshots help resolve disputes if any issues arise")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_handoff_cancel(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.views import ConfirmCancelView
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        embed = create_error_embed("Access Denied", "You are not part of this trade.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    embed = discord.Embed(
        title="⚠️ Cancel Trade?",
        description=f"Are you sure you want to cancel Trade #{trade_id}?\n\nThis action cannot be undone.",
        color=0xF1C40F
    )
    
    view = ConfirmCancelView(trade_id, interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def handle_handoff_tips(interaction: discord.Interaction):
    embed = discord.Embed(
        title="💡 In-Game Trading Tips",
        description="Follow these tips for safe and successful trades!",
        color=0xF39C12
    )
    embed.add_field(
        name="📋 Before Trading",
        value="• Verify the other player's Roblox username\n"
              "• Double-check the agreed items and quantities\n"
              "• Enable screen recording if possible",
        inline=False
    )
    embed.add_field(
        name="🔄 During the Trade",
        value="• Check items carefully in the trade window\n"
              "• Make sure quantities match\n"
              "• Never rush - take your time\n"
              "• Screenshot before clicking accept",
        inline=False
    )
    embed.add_field(
        name="✅ After Trading",
        value="• Confirm the trade in Discord\n"
              "• Keep your proof for at least 7 days\n"
              "• Report any issues immediately",
        inline=False
    )
    embed.set_footer(text="Stay safe and happy trading! 🎮")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_ticket_roblox(interaction: discord.Interaction):
    from ui.views import RobloxUsernameModal
    modal = RobloxUsernameModal(0)
    await interaction.response.send_modal(modal)


async def handle_ticket_confirm(interaction: discord.Interaction, trade_id: int):
    await handle_handoff_confirm(interaction, trade_id)


async def handle_ticket_safety(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛡️ Trade Safety Checklist",
        description="Complete this checklist for a safe trade:",
        color=0xF1C40F
    )
    embed.add_field(
        name="Before Trading",
        value="☐ Verified the other player's username\n"
              "☐ Double-checked items being traded\n"
              "☐ Confirmed the agreed values\n"
              "☐ Screenshots ready to record",
        inline=False
    )
    embed.add_field(
        name="During Trade",
        value="☐ In the same Roblox server\n"
              "☐ Items in trade window match agreement\n"
              "☐ No extra items requested\n"
              "☐ Screenshot before accepting",
        inline=False
    )
    embed.add_field(
        name="After Trading",
        value="☐ Received correct items\n"
              "☐ Upload proof if needed\n"
              "☐ Confirm in Discord\n"
              "☐ Report issues immediately",
        inline=False
    )
    embed.set_footer(text="Stay safe and report scammers!")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_ticket_items(interaction: discord.Interaction, trade_id: int):
    await handle_trade_details(interaction, trade_id)


async def handle_ticket_proof(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📸 Upload Trade Proof",
        description="To upload proof of your trade:",
        color=0x3498DB
    )
    embed.add_field(
        name="Instructions",
        value="1. Take a screenshot of the completed trade\n"
              "2. Reply to this message with your screenshot\n"
              "3. The image will be saved as proof",
        inline=False
    )
    embed.set_footer(text="Keep screenshots for at least 7 days")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_ticket_invitemod(interaction: discord.Interaction, trade_id: Optional[int]):
    from utils.database import get_guild_settings
    
    if not interaction.guild:
        embed = create_error_embed("Error", "This feature only works in a server.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    settings = await get_guild_settings(interaction.guild.id)
    mod_role_id = settings.get('mod_role_id') if settings else None
    
    if mod_role_id:
        mod_role = interaction.guild.get_role(mod_role_id)
        if mod_role:
            trade_info = f" for Trade #{trade_id}" if trade_id else ""
            embed = discord.Embed(
                title="🚨 Moderator Requested",
                description=f"A moderator has been called{trade_info}.",
                color=0xE74C3C
            )
            embed.add_field(name="Requested By", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(
                content=mod_role.mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True)
            )
            return
    
    embed = create_info_embed(
        "Moderator Not Set",
        "No moderator role is configured.\nPlease contact server staff directly.\n\n**Tip:** Admins can set a mod role with `/settings modrole`"
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_ticket_issue(interaction: discord.Interaction, trade_id: int):
    await handle_handoff_issue(interaction, trade_id)


async def handle_ticket_close(interaction: discord.Interaction, trade_id: Optional[int]):
    from utils.database import get_trade, close_trade_ticket, update_trade
    
    if trade_id:
        trade = await safe_fetch_trade(trade_id)
        if trade and trade['status'] not in ('completed', 'cancelled', 'disputed'):
            embed = discord.Embed(
                title="⚠️ Trade Not Complete",
                description="This trade hasn't been completed yet.\nClosing will cancel the trade.",
                color=0xF1C40F
            )
            from ui.views import ConfirmCloseView
            view = ConfirmCloseView(trade_id, interaction.user.id)
            return await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        await close_trade_ticket(trade_id)
    
    embed = discord.Embed(
        title="🔒 Ticket Closed",
        description="This trade ticket has been closed.",
        color=0x95A5A6
    )
    await interaction.response.send_message(embed=embed)
    
    if isinstance(interaction.channel, discord.Thread):
        import asyncio
        await asyncio.sleep(5)
        try:
            await interaction.channel.edit(archived=True)
        except:
            pass


async def handle_announce_interested(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    requester_id = trade['requester_id']
    if interaction.user.id == requester_id:
        embed = create_error_embed("Oops!", "You can't express interest in your own trade!")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    requester = await safe_fetch_user(interaction.client, requester_id)
    
    game = trade['game']
    game_emoji = GAME_EMOJIS.get(game, '🎮')
    game_color = GAME_COLORS.get(game, 0x2ECC71)
    
    embed = discord.Embed(
        title=f"{game_emoji} Someone is Interested!",
        description=f"{interaction.user.mention} is interested in Trade #{trade_id}!",
        color=game_color
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="Next Step", value="DM them to discuss the trade!", inline=False)
    
    try:
        if requester:
            await requester.send(embed=embed)
        embed = create_success_embed("Interest Sent!", f"Your interest has been sent to {requester.display_name if requester else 'the trader'}!", game)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except:
        embed = create_info_embed("DMs Disabled", f"Couldn't DM the trader. Tag them directly: {requester.mention if requester else ''}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_announce_items(interaction: discord.Interaction, trade_id: int):
    await handle_trade_details(interaction, trade_id)


async def handle_announce_profile(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, get_user
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    requester_id = trade['requester_id']
    user = await safe_fetch_user(interaction.client, requester_id)
    user_data = await get_user(requester_id)
    
    embed = discord.Embed(
        title=f"👤 {user.display_name if user else 'Trader'}'s Profile",
        color=0x3498DB
    )
    
    if user:
        embed.set_thumbnail(url=user.display_avatar.url)
    
    if user_data:
        trust_tier = user_data.get('trust_tier', 'Bronze')
        tier_emoji = TIER_EMOJIS.get(trust_tier, "🏅")
        trust_score = user_data.get('trust_score', 50)
        
        embed.add_field(name="Trust Score", value=f"{trust_score:.1f}/100", inline=True)
        embed.add_field(name="Trust Tier", value=f"{tier_emoji} {trust_tier}", inline=True)
        embed.add_field(name="Total Trades", value=str(user_data.get('total_trades', 0)), inline=True)
        embed.add_field(name="Successful", value=str(user_data.get('successful_trades', 0)), inline=True)
        embed.add_field(name="Disputed", value=str(user_data.get('disputed_trades', 0)), inline=True)
    else:
        embed.description = "This user is new to trading!"
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_announce_share(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    game = trade['game']
    game_name = GAME_NAMES.get(game, game)
    game_emoji = GAME_EMOJIS.get(game, '🎮')
    
    items_str = trade.get('requester_items', '[]')
    items = json.loads(items_str) if items_str else []
    items_preview = ", ".join([i['name'] for i in items[:3]])
    if len(items) > 3:
        items_preview += f" +{len(items) - 3} more"
    
    share_text = f"{game_emoji} Trade #{trade_id} | {game_name}\n📦 Items: {items_preview}"
    
    embed = discord.Embed(
        title="📤 Share This Trade",
        description=f"```\n{share_text}\n```",
        color=0x3498DB
    )
    embed.set_footer(text="Copy and paste to share with friends!")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_counter_accept(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history
    from ui.views import DynamicHandoffView
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id != trade['requester_id']:
        embed = create_error_embed("Access Denied", "Only the original trader can accept this counter.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    try:
        await update_trade(trade_id, status='accepted')
        await add_trade_history(trade_id, 'counter_accepted', interaction.user.id)
    except Exception as e:
        logger.error(f"Error accepting counter: {e}")
        embed = create_error_embed("Error", "Failed to accept counter offer.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    await disable_message_buttons(interaction)
    
    target = await safe_fetch_user(interaction.client, trade['target_id'])
    game = trade['game']
    game_color = GAME_COLORS.get(game, 0x2ECC71)
    
    embed = discord.Embed(
        title="✅ Counter Offer Accepted!",
        description=f"Both parties have agreed on the terms for Trade #{trade_id}.",
        color=game_color
    )
    embed.add_field(name="Next Step", value="Complete the trade in Roblox and confirm below!", inline=False)
    
    handoff_view = DynamicHandoffView(trade_id, trade['requester_id'], trade['target_id'])
    await interaction.response.send_message(
        content=f"{interaction.user.mention} {target.mention if target else ''}",
        embed=embed,
        view=handoff_view
    )


async def handle_counter_decline(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id != trade['requester_id']:
        embed = create_error_embed("Access Denied", "Only the original trader can decline.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    try:
        await update_trade(trade_id, status='pending', counter_offer_data=None)
        await add_trade_history(trade_id, 'counter_declined', interaction.user.id)
    except Exception as e:
        logger.error(f"Error declining counter: {e}")
    
    await disable_message_buttons(interaction)
    
    embed = discord.Embed(
        title="❌ Counter Offer Declined",
        description=f"The counter offer for Trade #{trade_id} was not accepted.\nThe original trade is still pending.",
        color=0xE74C3C
    )
    await interaction.response.send_message(embed=embed)


async def handle_counter_again(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.views import CounterOfferModal
    
    trade = await safe_fetch_trade(trade_id)
    if not trade:
        embed = create_error_embed("Trade Not Found", "This trade no longer exists.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if interaction.user.id != trade['requester_id']:
        embed = create_error_embed("Access Denied", "Only the original trader can counter.")
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    modal = CounterOfferModal(trade_id, trade['game'], trade['target_id'])
    await interaction.response.send_modal(modal)


async def handle_persistent_interaction(bot, interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return False
    
    custom_id = interaction.data.get('custom_id', '') if interaction.data else ''
    if not custom_id:
        return False
    
    handlers = {
        'trade:accept:': handle_trade_accept,
        'trade:decline:': handle_trade_decline,
        'trade:counter:': handle_trade_counter,
        'trade:negotiate:': handle_trade_negotiate,
        'trade:details:': handle_trade_details,
        'trade:profile:': handle_trade_profile,
        'trade:message:': lambda i, t: handle_trade_profile(i, t),
        'trade:share:': handle_announce_share,
        'trade:bookmark:': lambda i, t: i.response.send_message(f"Trade #{t} bookmarked!", ephemeral=True),
        'trade:report:': lambda i, t: handle_handoff_issue(i, t),
        'handoff:confirm:': handle_handoff_confirm,
        'handoff:issue:': handle_handoff_issue,
        'handoff:proof:': handle_handoff_proof,
        'handoff:cancel:': handle_handoff_cancel,
        'ticket:roblox:': lambda i, t: handle_ticket_roblox(i),
        'ticket:confirm:': handle_ticket_confirm,
        'ticket:safety:': lambda i, t: handle_ticket_safety(i),
        'ticket:items:': handle_ticket_items,
        'ticket:proof:': lambda i, t: handle_ticket_proof(i),
        'ticket:invitemod:': handle_ticket_invitemod,
        'ticket:issue:': handle_ticket_issue,
        'ticket:close:': handle_ticket_close,
        'announce:interested:': handle_announce_interested,
        'announce:items:': handle_announce_items,
        'announce:profile:': handle_announce_profile,
        'announce:share:': handle_announce_share,
        'counter:accept:': handle_counter_accept,
        'counter:decline:': handle_counter_decline,
        'counter:again:': handle_counter_again,
    }
    
    for prefix, handler in handlers.items():
        if custom_id.startswith(prefix):
            match = re.search(r':(\d+)$', custom_id)
            trade_id = int(match.group(1)) if match else None
            try:
                if trade_id is not None:
                    await handler(interaction, trade_id)
                else:
                    await handler(interaction, 0)
            except Exception as e:
                logger.error(f"Error handling {prefix}: {e}")
                try:
                    if not interaction.response.is_done():
                        embed = create_error_embed("Error", "Something went wrong. Please try again.")
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                except:
                    pass
            return True
    
    if custom_id == 'trade:help:global':
        await handle_trade_help(interaction)
        return True
    
    if custom_id == 'handoff:tips:global':
        await handle_handoff_tips(interaction)
        return True
    
    return False


def setup_persistent_views(bot):
    @bot.event
    async def on_interaction(interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            try:
                await handle_persistent_interaction(bot, interaction)
            except Exception as e:
                logger.error(f"Error handling component interaction: {e}")
                if not interaction.response.is_done():
                    try:
                        embed = create_error_embed("Error", "Something went wrong. Please try again.")
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                    except:
                        pass
    
    logger.info("Persistent interaction handler registered successfully")
