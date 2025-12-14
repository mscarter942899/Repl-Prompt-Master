import discord
from discord.ui import View
import json
import re
from datetime import datetime


async def handle_persistent_interaction(bot, interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return False
    
    custom_id = interaction.data.get('custom_id', '') if interaction.data else ''
    if not custom_id:
        return False
    
    if custom_id.startswith('trade:accept:'):
        match = re.match(r'trade:accept:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_accept(interaction, trade_id)
            return True
    
    elif custom_id.startswith('trade:decline:'):
        match = re.match(r'trade:decline:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_decline(interaction, trade_id)
            return True
    
    elif custom_id.startswith('trade:counter:'):
        match = re.match(r'trade:counter:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_counter(interaction, trade_id)
            return True
    
    elif custom_id.startswith('trade:negotiate:'):
        match = re.match(r'trade:negotiate:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_negotiate(interaction, trade_id)
            return True
    
    elif custom_id.startswith('trade:details:'):
        match = re.match(r'trade:details:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_details(interaction, trade_id)
            return True
    
    elif custom_id.startswith('trade:profile:'):
        match = re.match(r'trade:profile:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_profile(interaction, trade_id)
            return True
    
    elif custom_id.startswith('trade:message:'):
        match = re.match(r'trade:message:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_message(interaction, trade_id)
            return True
    
    elif custom_id.startswith('trade:share:'):
        match = re.match(r'trade:share:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_share(interaction, trade_id)
            return True
    
    elif custom_id.startswith('trade:bookmark:'):
        match = re.match(r'trade:bookmark:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_bookmark(interaction, trade_id)
            return True
    
    elif custom_id.startswith('trade:report:'):
        match = re.match(r'trade:report:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_trade_report(interaction, trade_id)
            return True
    
    elif custom_id == 'trade:help:global':
        await handle_trade_help(interaction)
        return True
    
    elif custom_id.startswith('handoff:confirm:'):
        match = re.match(r'handoff:confirm:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_handoff_confirm(interaction, trade_id)
            return True
    
    elif custom_id.startswith('handoff:issue:'):
        match = re.match(r'handoff:issue:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_handoff_issue(interaction, trade_id)
            return True
    
    elif custom_id.startswith('handoff:proof:'):
        match = re.match(r'handoff:proof:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_handoff_proof(interaction, trade_id)
            return True
    
    elif custom_id.startswith('handoff:cancel:'):
        match = re.match(r'handoff:cancel:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_handoff_cancel(interaction, trade_id)
            return True
    
    elif custom_id == 'handoff:tips:global':
        await handle_handoff_tips(interaction)
        return True
    
    elif custom_id.startswith('announce:interested:'):
        match = re.match(r'announce:interested:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_announce_interested(interaction, trade_id)
            return True
    
    elif custom_id.startswith('announce:items:'):
        match = re.match(r'announce:items:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_announce_items(interaction, trade_id)
            return True
    
    elif custom_id.startswith('announce:profile:'):
        match = re.match(r'announce:profile:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_announce_profile(interaction, trade_id)
            return True
    
    elif custom_id.startswith('announce:share:'):
        match = re.match(r'announce:share:(\d+)', custom_id)
        if match:
            trade_id = int(match.group(1))
            await handle_announce_share(interaction, trade_id)
            return True
    
    return False


async def disable_message_buttons(interaction: discord.Interaction):
    if interaction.message:
        try:
            from discord.ui import Button as UIButton
            disabled_view = View(timeout=None)
            for action_row in interaction.message.components:
                if hasattr(action_row, 'children'):
                    for child in action_row.children:  # type: ignore
                        if hasattr(child, 'custom_id') and hasattr(child, 'label'):
                            btn = UIButton(
                                label=getattr(child, 'label', 'Button') or 'Button',
                                style=getattr(child, 'style', discord.ButtonStyle.secondary),  # type: ignore
                                custom_id=getattr(child, 'custom_id', ''),
                                disabled=True,
                                emoji=getattr(child, 'emoji', None),
                            )
                            disabled_view.add_item(btn)
            if disabled_view.children:
                await interaction.message.edit(view=disabled_view)
        except Exception:
            pass


async def handle_trade_accept(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history
    from ui.views import DynamicHandoffView
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    if interaction.user.id != trade['target_id']:
        await interaction.response.send_message("Only the trade recipient can accept this trade.", ephemeral=True)
        return
    
    await update_trade(trade_id, status='accepted')
    await add_trade_history(trade_id, 'accepted', interaction.user.id)
    
    await interaction.response.send_message("Trade accepted! Complete the trade in-game and confirm below.", ephemeral=False)
    await disable_message_buttons(interaction)
    
    handoff_view = DynamicHandoffView(trade_id, trade['requester_id'], trade['target_id'])
    requester = await interaction.client.fetch_user(trade['requester_id'])
    await interaction.followup.send(
        f"{requester.mention} {interaction.user.mention} - Complete your trade in-game and confirm below!",
        view=handoff_view
    )


async def handle_trade_decline(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
        return
    
    await update_trade(trade_id, status='cancelled')
    await add_trade_history(trade_id, 'declined', interaction.user.id)
    
    await disable_message_buttons(interaction)
    await interaction.response.send_message("Trade has been declined.", ephemeral=False)


async def handle_trade_counter(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    if interaction.user.id != trade['target_id']:
        await interaction.response.send_message("Only the trade recipient can make a counter offer.", ephemeral=True)
        return
    
    await interaction.response.send_message(
        "To make a counter offer, use `/trade create` and select the same game. Tag the original trader as the target user.",
        ephemeral=True
    )


async def handle_trade_negotiate(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.views import NegotiateModal
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
        return
    
    modal = NegotiateModal(trade_id)
    await interaction.response.send_modal(modal)


async def handle_trade_details(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.embeds import GAME_NAMES
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    items_str = trade.get('requester_items', '[]')
    items = json.loads(items_str) if items_str else []
    
    embed = discord.Embed(title=f"Trade #{trade_id} Details", color=0x3498DB)
    embed.add_field(name="Game", value=GAME_NAMES.get(trade['game'], trade['game']), inline=True)
    embed.add_field(name="Status", value=trade['status'].replace('_', ' ').title(), inline=True)
    embed.add_field(name="Risk Level", value=trade.get('risk_level', 'Unknown').title(), inline=True)
    
    if items:
        items_list = "\n".join([f"• {i['name']} ({i.get('rarity', 'Common')})" for i in items[:10]])
        if len(items) > 10:
            items_list += f"\n... and {len(items) - 10} more"
        embed.add_field(name="Items Offered", value=items_list, inline=False)
    
    total_value = sum(i.get('value', 0) for i in items)
    embed.add_field(name="Total Value", value=f"{total_value:,.0f}", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_trade_profile(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, get_user
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    other_id = trade['target_id'] if interaction.user.id == trade['requester_id'] else trade['requester_id']
    other_user = await interaction.client.fetch_user(other_id)
    user_data = await get_user(other_id)
    
    embed = discord.Embed(title=f"{other_user.display_name}'s Profile", color=0x9B59B6)
    embed.set_thumbnail(url=other_user.display_avatar.url)
    
    if user_data:
        trust_tier = user_data.get('trust_tier', 'Bronze')
        tier_emoji = {"Bronze": "🥉", "Silver": "🥈", "Gold": "🥇", "Platinum": "💎", "Diamond": "💠"}.get(trust_tier, "🏅")
        
        embed.add_field(name="Trust Score", value=f"{user_data.get('trust_score', 50):.1f}/100", inline=True)
        embed.add_field(name="Trust Tier", value=f"{tier_emoji} {trust_tier}", inline=True)
        embed.add_field(name="Total Trades", value=str(user_data.get('total_trades', 0)), inline=True)
        embed.add_field(name="Successful", value=str(user_data.get('successful_trades', 0)), inline=True)
        embed.add_field(name="Disputed", value=str(user_data.get('disputed_trades', 0)), inline=True)
    else:
        embed.description = "This user hasn't made any trades yet."
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_trade_message(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
        return
    
    other_id = trade['target_id'] if interaction.user.id == trade['requester_id'] else trade['requester_id']
    other_user = await interaction.client.fetch_user(other_id)
    
    await interaction.response.send_message(
        f"Send a direct message to {other_user.mention} to discuss the trade!",
        ephemeral=True
    )


async def handle_trade_share(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.embeds import GAME_NAMES
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    items_str = trade.get('requester_items', '[]')
    items = json.loads(items_str) if items_str else []
    items_preview = ", ".join([i['name'] for i in items[:3]])
    if len(items) > 3:
        items_preview += f" +{len(items) - 3} more"
    
    share_text = f"Trade #{trade_id} | {GAME_NAMES.get(trade['game'], trade['game'])}\nItems: {items_preview}"
    await interaction.response.send_message(f"Share this:\n```\n{share_text}\n```", ephemeral=True)


async def handle_trade_bookmark(interaction: discord.Interaction, trade_id: int):
    await interaction.response.send_message(f"Trade #{trade_id} bookmarked! Use `/trade view {trade_id}` anytime.", ephemeral=True)


async def handle_trade_report(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.views import ReportModal
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    reported_id = trade['requester_id'] if interaction.user.id == trade['target_id'] else trade['target_id']
    modal = ReportModal(trade_id, reported_id)
    await interaction.response.send_modal(modal)


async def handle_trade_help(interaction: discord.Interaction):
    embed = discord.Embed(title="Trade Help Guide", color=0x3498DB, description="Here's how trading works:")
    embed.add_field(name="1. Accept/Decline", value="The recipient can accept or decline the trade offer.", inline=False)
    embed.add_field(name="2. Counter Offer", value="Don't like the deal? Make a counter offer.", inline=False)
    embed.add_field(name="3. Negotiate", value="Send a message to discuss terms.", inline=False)
    embed.add_field(name="4. In-Game Trade", value="Once accepted, trade in the actual Roblox game.", inline=False)
    embed.add_field(name="5. Confirm", value="Both users confirm the trade was completed.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_handoff_confirm(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history, get_user, update_user
    from utils.trust_engine import trust_engine
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    requester_id = trade['requester_id']
    target_id = trade['target_id']
    
    if interaction.user.id not in (requester_id, target_id):
        await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
        return
    
    field = 'requester_confirmed' if interaction.user.id == requester_id else 'target_confirmed'
    await update_trade(trade_id, **{field: 1})
    
    trade = await get_trade(trade_id)
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
        
        embed = discord.Embed(title="Trade Completed!", color=0x2ECC71, description=f"Trade #{trade_id} verified.")
        embed.add_field(name="Receipt", value=f"`{receipt_hash[:32]}...`", inline=False)
        embed.set_footer(text="Trust scores updated!")
        
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Confirmed! Waiting for the other party...", ephemeral=True)


async def handle_handoff_issue(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, update_trade, add_trade_history
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
        return
    
    await update_trade(trade_id, status='disputed')
    await add_trade_history(trade_id, 'disputed', interaction.user.id)
    
    await disable_message_buttons(interaction)
    await interaction.response.send_message("Trade disputed. A moderator will review.", ephemeral=False)


async def handle_handoff_proof(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
        return
    
    await interaction.response.send_message("Reply with a screenshot of the completed in-game trade.", ephemeral=True)


async def handle_handoff_cancel(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.views import ConfirmCancelView
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    if interaction.user.id not in (trade['requester_id'], trade['target_id']):
        await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
        return
    
    view = ConfirmCancelView(trade_id, interaction.user.id)
    await interaction.response.send_message("Are you sure you want to cancel?", view=view, ephemeral=True)


async def handle_handoff_tips(interaction: discord.Interaction):
    embed = discord.Embed(title="In-Game Trading Tips", color=0xF39C12)
    embed.add_field(name="Before", value="• Double-check items\n• Verify quantities\n• Confirm trader identity", inline=False)
    embed.add_field(name="During", value="• Screenshot before confirming\n• Don't rush\n• Decline if suspicious", inline=False)
    embed.add_field(name="After", value="• Confirm here\n• Keep proof 7 days", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_announce_interested(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    requester_id = trade['requester_id']
    if interaction.user.id == requester_id:
        await interaction.response.send_message("You can't express interest in your own trade!", ephemeral=True)
        return
    
    requester = await interaction.client.fetch_user(requester_id)
    
    embed = discord.Embed(title="Someone is Interested!", color=0x2ECC71)
    embed.description = f"{interaction.user.mention} is interested in Trade #{trade_id}!"
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    
    try:
        await requester.send(embed=embed)
        await interaction.response.send_message(f"Interest sent to {requester.display_name}!", ephemeral=True)
    except:
        await interaction.response.send_message(f"Couldn't DM trader. Tag them: {requester.mention}", ephemeral=True)


async def handle_announce_items(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.embeds import GAME_NAMES
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    items_str = trade.get('requester_items', '[]')
    items = json.loads(items_str) if items_str else []
    
    embed = discord.Embed(title=f"Items in Trade #{trade_id}", color=0x9B59B6)
    embed.add_field(name="Game", value=GAME_NAMES.get(trade['game'], trade['game']), inline=True)
    
    if items:
        for item in items[:10]:
            rarity = item.get('rarity', 'Common')
            embed.add_field(name=item['name'], value=f"Rarity: {rarity}", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_announce_profile(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade, get_user
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    requester_id = trade['requester_id']
    user = await interaction.client.fetch_user(requester_id)
    user_data = await get_user(requester_id)
    
    embed = discord.Embed(title=f"{user.display_name}'s Profile", color=0x3498DB)
    embed.set_thumbnail(url=user.display_avatar.url)
    
    if user_data:
        trust_tier = user_data.get('trust_tier', 'Bronze')
        tier_emoji = {"Bronze": "🥉", "Silver": "🥈", "Gold": "🥇", "Platinum": "💎", "Diamond": "💠"}.get(trust_tier, "🏅")
        
        embed.add_field(name="Trust Score", value=f"{user_data.get('trust_score', 50):.1f}/100", inline=True)
        embed.add_field(name="Trust Tier", value=f"{tier_emoji} {trust_tier}", inline=True)
        embed.add_field(name="Total Trades", value=str(user_data.get('total_trades', 0)), inline=True)
        embed.add_field(name="Successful", value=str(user_data.get('successful_trades', 0)), inline=True)
        embed.add_field(name="Disputed", value=str(user_data.get('disputed_trades', 0)), inline=True)
    else:
        embed.description = "This user hasn't made any trades yet."
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_announce_share(interaction: discord.Interaction, trade_id: int):
    from utils.database import get_trade
    from ui.embeds import GAME_NAMES
    
    trade = await get_trade(trade_id)
    if not trade:
        await interaction.response.send_message("Trade not found.", ephemeral=True)
        return
    
    items_str = trade.get('requester_items', '[]')
    items = json.loads(items_str) if items_str else []
    items_preview = ", ".join([i['name'] for i in items[:3]])
    if len(items) > 3:
        items_preview += f" +{len(items) - 3} more"
    
    share_text = f"Trade #{trade_id} | {GAME_NAMES.get(trade['game'], trade['game'])}\nItems: {items_preview}"
    await interaction.response.send_message(f"Share this:\n```\n{share_text}\n```", ephemeral=True)


def setup_persistent_views(bot):
    @bot.event
    async def on_interaction(interaction: discord.Interaction):
        handled = await handle_persistent_interaction(bot, interaction)
        if not handled:
            pass
