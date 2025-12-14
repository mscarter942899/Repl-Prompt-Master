import discord
from discord.ui import View, Button, Select, Modal, TextInput
from typing import Optional, List, Dict
import json


class DynamicTradeView(View):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(timeout=None)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
        
        self.add_item(AcceptButton(trade_id, requester_id, target_id))
        self.add_item(DeclineButton(trade_id, requester_id, target_id))
        self.add_item(CounterButton(trade_id, target_id))
        self.add_item(NegotiateButton(trade_id, requester_id, target_id))
        self.add_item(ViewDetailsButton(trade_id))
        self.add_item(ViewProfileButton(trade_id, requester_id, target_id))
        self.add_item(MessageButton(trade_id, requester_id, target_id))
        self.add_item(ShareButton(trade_id))
        self.add_item(BookmarkButton(trade_id))
        self.add_item(ReportButton(trade_id, requester_id, target_id))
        self.add_item(HelpButton())


class AcceptButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Accept Trade", style=discord.ButtonStyle.success, emoji="✅", custom_id=f"trade:accept:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("Only the trade recipient can accept this trade.", ephemeral=True)
            return
        
        from utils.database import update_trade, add_trade_history
        await update_trade(self.trade_id, status='accepted')
        await add_trade_history(self.trade_id, 'accepted', interaction.user.id)
        
        await interaction.response.send_message("Trade accepted! Complete the trade in-game and confirm below.", ephemeral=False)
        
        if self.view:
            for child in self.view.children:
                if hasattr(child, 'disabled'):
                    child.disabled = True
            if interaction.message:
                await interaction.message.edit(view=self.view)
        
        handoff_view = DynamicHandoffView(self.trade_id, self.requester_id, self.target_id)
        requester = await interaction.client.fetch_user(self.requester_id)
        await interaction.followup.send(
            f"{requester.mention} {interaction.user.mention} - Complete your trade in-game and confirm below!",
            view=handoff_view
        )


class DeclineButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Decline", style=discord.ButtonStyle.danger, emoji="❌", custom_id=f"trade:decline:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        from utils.database import update_trade, add_trade_history
        await update_trade(self.trade_id, status='cancelled')
        await add_trade_history(self.trade_id, 'declined', interaction.user.id)
        
        if self.view:
            for child in self.view.children:
                if hasattr(child, 'disabled'):
                    child.disabled = True
            if interaction.message:
                await interaction.message.edit(view=self.view)
        
        await interaction.response.send_message("Trade has been declined.", ephemeral=False)


class CounterButton(Button):
    def __init__(self, trade_id: int, target_id: int):
        super().__init__(label="Counter Offer", style=discord.ButtonStyle.primary, emoji="🔄", custom_id=f"trade:counter:{trade_id}", row=0)
        self.trade_id = trade_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("Only the trade recipient can make a counter offer.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            "To make a counter offer, use `/trade create` and select the same game. Tag the original trader as the target user.",
            ephemeral=True
        )


class NegotiateButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Negotiate", style=discord.ButtonStyle.secondary, emoji="💬", custom_id=f"trade:negotiate:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        modal = NegotiateModal(self.trade_id)
        await interaction.response.send_modal(modal)


class ViewDetailsButton(Button):
    def __init__(self, trade_id: int):
        super().__init__(label="View Details", style=discord.ButtonStyle.secondary, emoji="📋", custom_id=f"trade:details:{trade_id}", row=1)
        self.trade_id = trade_id
    
    async def callback(self, interaction: discord.Interaction):
        from utils.database import get_trade, get_user
        from ui.embeds import GAME_NAMES
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        items_str = trade.get('requester_items', '[]')
        items = json.loads(items_str) if items_str else []
        
        embed = discord.Embed(title=f"Trade #{self.trade_id} Details", color=0x3498DB)
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


class ViewProfileButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="View Profile", style=discord.ButtonStyle.secondary, emoji="👤", custom_id=f"trade:profile:{trade_id}", row=1)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        from utils.database import get_user
        
        other_id = self.target_id if interaction.user.id == self.requester_id else self.requester_id
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


class MessageButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Message", style=discord.ButtonStyle.secondary, emoji="💌", custom_id=f"trade:message:{trade_id}", row=1)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        other_id = self.target_id if interaction.user.id == self.requester_id else self.requester_id
        other_user = await interaction.client.fetch_user(other_id)
        
        await interaction.response.send_message(
            f"Send a direct message to {other_user.mention} to discuss the trade!",
            ephemeral=True
        )


class ShareButton(Button):
    def __init__(self, trade_id: int):
        super().__init__(label="Share", style=discord.ButtonStyle.secondary, emoji="📤", custom_id=f"trade:share:{trade_id}", row=1)
        self.trade_id = trade_id
    
    async def callback(self, interaction: discord.Interaction):
        from utils.database import get_trade
        from ui.embeds import GAME_NAMES
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        items_str = trade.get('requester_items', '[]')
        items = json.loads(items_str) if items_str else []
        items_preview = ", ".join([i['name'] for i in items[:3]])
        if len(items) > 3:
            items_preview += f" +{len(items) - 3} more"
        
        share_text = f"Trade #{self.trade_id} | {GAME_NAMES.get(trade['game'], trade['game'])}\nItems: {items_preview}"
        await interaction.response.send_message(f"Share this:\n```\n{share_text}\n```", ephemeral=True)


class BookmarkButton(Button):
    def __init__(self, trade_id: int):
        super().__init__(label="Bookmark", style=discord.ButtonStyle.secondary, emoji="🔖", custom_id=f"trade:bookmark:{trade_id}", row=2)
        self.trade_id = trade_id
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Trade #{self.trade_id} bookmarked! Use `/trade view {self.trade_id}` anytime.", ephemeral=True)


class ReportButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Report", style=discord.ButtonStyle.danger, emoji="🚨", custom_id=f"trade:report:{trade_id}", row=2)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        reported_id = self.requester_id if interaction.user.id == self.target_id else self.target_id
        modal = ReportModal(self.trade_id, reported_id)
        await interaction.response.send_modal(modal)


class HelpButton(Button):
    def __init__(self):
        super().__init__(label="Help", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="trade:help:global", row=2)
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Trade Help Guide", color=0x3498DB, description="Here's how trading works:")
        embed.add_field(name="1. Accept/Decline", value="The recipient can accept or decline the trade offer.", inline=False)
        embed.add_field(name="2. Counter Offer", value="Don't like the deal? Make a counter offer.", inline=False)
        embed.add_field(name="3. Negotiate", value="Send a message to discuss terms.", inline=False)
        embed.add_field(name="4. In-Game Trade", value="Once accepted, trade in the actual Roblox game.", inline=False)
        embed.add_field(name="5. Confirm", value="Both users confirm the trade was completed.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DynamicHandoffView(View):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(timeout=None)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
        
        self.add_item(ConfirmTradeButton(trade_id, requester_id, target_id))
        self.add_item(ReportIssueButton(trade_id, requester_id, target_id))
        self.add_item(UploadProofButton(trade_id, requester_id, target_id))
        self.add_item(CancelTradeButton(trade_id, requester_id, target_id))
        self.add_item(TradingTipsButton())


class ConfirmTradeButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="I Completed Trade", style=discord.ButtonStyle.success, emoji="✅", custom_id=f"handoff:confirm:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        from utils.database import get_trade, update_trade, add_trade_history, get_user, update_user
        from utils.trust_engine import trust_engine
        from datetime import datetime
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        field = 'requester_confirmed' if interaction.user.id == self.requester_id else 'target_confirmed'
        await update_trade(self.trade_id, **{field: 1})
        
        trade = await get_trade(self.trade_id)
        if trade and trade['requester_confirmed'] and trade['target_confirmed']:
            await update_trade(self.trade_id, status='completed', completed_at=datetime.utcnow().isoformat())
            await add_trade_history(self.trade_id, 'completed', 0)
            
            requester_data = await get_user(self.requester_id)
            target_data = await get_user(self.target_id)
            
            if requester_data:
                req_updates = trust_engine.update_reputation(requester_data, 'trade_completed')
                await update_user(self.requester_id, **req_updates)
            if target_data:
                tgt_updates = trust_engine.update_reputation(target_data, 'trade_completed')
                await update_user(self.target_id, **tgt_updates)
            
            if self.view:
                for child in self.view.children:
                    if hasattr(child, 'disabled'):
                        child.disabled = True
                if interaction.message:
                    await interaction.message.edit(view=self.view)
            
            receipt_hash = trust_engine.generate_receipt_hash(trade)
            await update_trade(self.trade_id, receipt_hash=receipt_hash)
            
            embed = discord.Embed(title="Trade Completed!", color=0x2ECC71, description=f"Trade #{self.trade_id} verified.")
            embed.add_field(name="Receipt", value=f"`{receipt_hash[:32]}...`", inline=False)
            embed.set_footer(text="Trust scores updated!")
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Confirmed! Waiting for the other party...", ephemeral=True)


class ReportIssueButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Something Went Wrong", style=discord.ButtonStyle.danger, emoji="⚠️", custom_id=f"handoff:issue:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        from utils.database import update_trade, add_trade_history
        await update_trade(self.trade_id, status='disputed')
        await add_trade_history(self.trade_id, 'disputed', interaction.user.id)
        
        if self.view:
            for child in self.view.children:
                if hasattr(child, 'disabled'):
                    child.disabled = True
            if interaction.message:
                await interaction.message.edit(view=self.view)
        
        await interaction.response.send_message("Trade disputed. A moderator will review.", ephemeral=False)


class UploadProofButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Upload Proof", style=discord.ButtonStyle.secondary, emoji="📸", custom_id=f"handoff:proof:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        await interaction.response.send_message("Reply with a screenshot of the completed in-game trade.", ephemeral=True)


class CancelTradeButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Cancel Trade", style=discord.ButtonStyle.secondary, emoji="🚫", custom_id=f"handoff:cancel:{trade_id}", row=1)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        view = ConfirmCancelView(self.trade_id, interaction.user.id)
        await interaction.response.send_message("Are you sure you want to cancel?", view=view, ephemeral=True)


class TradingTipsButton(Button):
    def __init__(self):
        super().__init__(label="Trading Tips", style=discord.ButtonStyle.secondary, emoji="💡", custom_id="handoff:tips:global", row=1)
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="In-Game Trading Tips", color=0xF39C12)
        embed.add_field(name="Before", value="• Double-check items\n• Verify quantities\n• Confirm trader identity", inline=False)
        embed.add_field(name="During", value="• Screenshot before confirming\n• Don't rush\n• Decline if suspicious", inline=False)
        embed.add_field(name="After", value="• Confirm here\n• Keep proof 7 days", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DynamicAnnouncementView(View):
    def __init__(self, trade_id: int, requester_id: int, game: str):
        super().__init__(timeout=None)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.game = game
        
        self.add_item(InterestedButton(trade_id, requester_id))
        self.add_item(ViewItemsButton(trade_id))
        self.add_item(TraderProfileButton(trade_id, requester_id))
        self.add_item(ShareAnnouncementButton(trade_id))


class InterestedButton(Button):
    def __init__(self, trade_id: int, requester_id: int):
        super().__init__(label="I'm Interested!", style=discord.ButtonStyle.success, emoji="🙋", custom_id=f"announce:interested:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id == self.requester_id:
            await interaction.response.send_message("You can't express interest in your own trade!", ephemeral=True)
            return
        
        requester = await interaction.client.fetch_user(self.requester_id)
        
        embed = discord.Embed(title="Someone is Interested!", color=0x2ECC71)
        embed.description = f"{interaction.user.mention} is interested in Trade #{self.trade_id}!"
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        try:
            await requester.send(embed=embed)
            await interaction.response.send_message(f"Interest sent to {requester.display_name}!", ephemeral=True)
        except:
            await interaction.response.send_message(f"Couldn't DM trader. Tag them: {requester.mention}", ephemeral=True)


class ViewItemsButton(Button):
    def __init__(self, trade_id: int):
        super().__init__(label="View Items", style=discord.ButtonStyle.secondary, emoji="📦", custom_id=f"announce:items:{trade_id}", row=0)
        self.trade_id = trade_id
    
    async def callback(self, interaction: discord.Interaction):
        from utils.database import get_trade
        from ui.embeds import GAME_NAMES
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        items_str = trade.get('requester_items', '[]')
        items = json.loads(items_str) if items_str else []
        
        embed = discord.Embed(title=f"Items in Trade #{self.trade_id}", color=0x9B59B6)
        embed.add_field(name="Game", value=GAME_NAMES.get(trade['game'], trade['game']), inline=True)
        
        if items:
            for item in items[:10]:
                rarity = item.get('rarity', 'Common')
                embed.add_field(name=item['name'], value=f"Rarity: {rarity}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TraderProfileButton(Button):
    def __init__(self, trade_id: int, requester_id: int):
        super().__init__(label="Trader Profile", style=discord.ButtonStyle.secondary, emoji="👤", custom_id=f"announce:profile:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
    
    async def callback(self, interaction: discord.Interaction):
        from utils.database import get_user
        
        user = await interaction.client.fetch_user(self.requester_id)
        user_data = await get_user(self.requester_id)
        
        embed = discord.Embed(title=f"{user.display_name}'s Profile", color=0x3498DB)
        embed.set_thumbnail(url=user.display_avatar.url)
        
        if user_data:
            embed.add_field(name="Trust", value=f"{user_data.get('trust_score', 50):.0f}/100", inline=True)
            embed.add_field(name="Trades", value=str(user_data.get('total_trades', 0)), inline=True)
        else:
            embed.description = "New trader with no history."
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ShareAnnouncementButton(Button):
    def __init__(self, trade_id: int):
        super().__init__(label="Share", style=discord.ButtonStyle.secondary, emoji="📤", custom_id=f"announce:share:{trade_id}", row=1)
        self.trade_id = trade_id
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Share: Trade #{self.trade_id} - Use `/trade view {self.trade_id}`", ephemeral=True)


class ConfirmCancelView(View):
    def __init__(self, trade_id: int, user_id: int):
        super().__init__(timeout=60)
        self.trade_id = trade_id
        self.user_id = user_id
    
    @discord.ui.button(label="Yes, Cancel", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        
        from utils.database import update_trade, add_trade_history
        await update_trade(self.trade_id, status='cancelled')
        await add_trade_history(self.trade_id, 'cancelled', interaction.user.id)
        await interaction.response.send_message("Trade cancelled.", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="No, Keep Trading", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_action(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.stop()


class NegotiateModal(Modal, title="Negotiate Trade"):
    message = TextInput(label="Your Message", placeholder="What would you like to discuss?", style=discord.TextStyle.paragraph, max_length=500)
    
    def __init__(self, trade_id: int):
        super().__init__()
        self.trade_id = trade_id
    
    async def on_submit(self, interaction: discord.Interaction):
        from utils.database import get_trade, add_trade_history
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        other_id = trade['target_id'] if interaction.user.id == trade['requester_id'] else trade['requester_id']
        other_user = await interaction.client.fetch_user(other_id)
        
        await add_trade_history(self.trade_id, 'negotiation', interaction.user.id, self.message.value)
        
        embed = discord.Embed(title=f"Negotiation - Trade #{self.trade_id}", color=0x3498DB, description=self.message.value)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        
        await interaction.response.send_message(f"{other_user.mention}", embed=embed)


class ReportModal(Modal, title="Report User"):
    reason = TextInput(label="Reason", placeholder="Describe what happened", style=discord.TextStyle.paragraph, max_length=1000)
    
    def __init__(self, trade_id: int, reported_id: int):
        super().__init__()
        self.trade_id = trade_id
        self.reported_id = reported_id
    
    async def on_submit(self, interaction: discord.Interaction):
        from utils.database import log_audit
        
        await log_audit('user_reported', interaction.user.id, self.reported_id, f"Trade {self.trade_id}: {self.reason.value}")
        
        embed = discord.Embed(title="Report Submitted", color=0xE74C3C, description="Your report will be reviewed by moderators.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TradeView(View):
    def __init__(self, trade_id: int, requester_id: int, target_id: int, timeout: float = 900):
        super().__init__(timeout=timeout)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
        self.result: Optional[str] = None
        self.message: Optional[discord.Message] = None
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("Only the trade recipient can accept.", ephemeral=True)
            return
        self.result = 'accepted'
        await interaction.response.send_message("Trade accepted!", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        self.result = 'declined'
        await interaction.response.send_message("Trade declined.", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="Counter", style=discord.ButtonStyle.primary, emoji="🔄")
    async def counter(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("Only recipient can counter.", ephemeral=True)
            return
        self.result = 'counter'
        await interaction.response.send_message("Use `/trade create` for counter offer.", ephemeral=True)
        self.stop()
    
    async def on_timeout(self):
        self.result = 'expired'
        if self.message:
            try:
                await self.message.edit(content="Trade expired.", view=None)
            except:
                pass


class HandoffView(View):
    def __init__(self, trade_id: int, requester_id: int, target_id: int, timeout: float = 900):
        super().__init__(timeout=timeout)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
        self.requester_confirmed = False
        self.target_confirmed = False
        self.result: Optional[str] = None
    
    @discord.ui.button(label="I traded in-game", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_trade(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.requester_id:
            self.requester_confirmed = True
        elif interaction.user.id == self.target_id:
            self.target_confirmed = True
        else:
            await interaction.response.send_message("Not part of trade.", ephemeral=True)
            return
        
        await interaction.response.send_message("Confirmed! Waiting for other party...", ephemeral=True)
        if self.requester_confirmed and self.target_confirmed:
            self.result = 'completed'
            self.stop()
    
    @discord.ui.button(label="Something went wrong", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def report_issue(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("Not part of trade.", ephemeral=True)
            return
        self.result = 'disputed'
        await interaction.response.send_message("Trade disputed.", ephemeral=True)
        self.stop()


class ConfirmView(View):
    def __init__(self, user_id: int, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.result: Optional[bool] = None
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        self.result = True
        await interaction.response.defer()
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        self.result = False
        await interaction.response.defer()
        self.stop()
    
    async def on_timeout(self):
        self.result = False


class PaginatorView(View):
    def __init__(self, pages: List[discord.Embed], user_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.user_id = user_id
        self.current_page = 0
        self.message: Optional[discord.Message] = None
        self._update_buttons()
    
    def _update_buttons(self):
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= len(self.pages) - 1
        self.last_page.disabled = self.current_page >= len(self.pages) - 1
    
    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        self.current_page = len(self.pages) - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except:
                pass


class GameSelectView(View):
    GAMES = [
        discord.SelectOption(label="Pet Simulator 99", value="ps99", emoji="🐾"),
        discord.SelectOption(label="Grow a Garden", value="gag", emoji="🌱"),
        discord.SelectOption(label="Adopt Me", value="am", emoji="🏠"),
        discord.SelectOption(label="Blox Fruits", value="bf", emoji="🍎"),
        discord.SelectOption(label="Steal a Brainrot", value="sab", emoji="🧠")
    ]
    
    def __init__(self, user_id: int, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.selected_game: Optional[str] = None
    
    @discord.ui.select(placeholder="Select a game...", options=GAMES)
    async def game_select(self, interaction: discord.Interaction, select: Select):
        if interaction.user.id != self.user_id:
            return
        self.selected_game = select.values[0]
        await interaction.response.defer()
        self.stop()
    
    async def on_timeout(self):
        self.selected_game = None


PersistentTradeView = DynamicTradeView
PersistentHandoffView = DynamicHandoffView
TradeAnnouncementView = DynamicAnnouncementView
