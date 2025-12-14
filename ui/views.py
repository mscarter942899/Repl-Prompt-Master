import discord
from discord.ui import View, Button, Select, Modal, TextInput
from typing import Optional, Callable, List, Dict, Any
import asyncio
import json


class PersistentTradeView(View):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(timeout=None)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    @discord.ui.button(label="Accept Trade", style=discord.ButtonStyle.success, emoji="✅", custom_id="trade:accept", row=0)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("Only the trade recipient can accept this trade.", ephemeral=True)
            return
        
        from utils.database import update_trade, add_trade_history
        await update_trade(self.trade_id, status='accepted')
        await add_trade_history(self.trade_id, 'accepted', interaction.user.id)
        
        await interaction.response.send_message(
            "Trade accepted! Both parties should now complete the trade in-game. Use the handoff buttons below to confirm.",
            ephemeral=False
        )
        
        for child in self.children:
            if hasattr(child, 'disabled'):
                child.disabled = True
        if interaction.message:
            await interaction.message.edit(view=self)
        
        handoff_view = PersistentHandoffView(self.trade_id, self.requester_id, self.target_id)
        requester = await interaction.client.fetch_user(self.requester_id)
        await interaction.followup.send(
            f"{requester.mention} {interaction.user.mention} - Complete your trade in-game and confirm below!",
            view=handoff_view
        )
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌", custom_id="trade:decline", row=0)
    async def decline(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        from utils.database import update_trade, add_trade_history
        await update_trade(self.trade_id, status='cancelled')
        await add_trade_history(self.trade_id, 'declined', interaction.user.id)
        
        for child in self.children:
            if hasattr(child, 'disabled'):
                child.disabled = True
        if interaction.message:
            await interaction.message.edit(view=self)
        
        await interaction.response.send_message("Trade has been declined.", ephemeral=False)
    
    @discord.ui.button(label="Counter Offer", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="trade:counter", row=0)
    async def counter(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("Only the trade recipient can make a counter offer.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            "To make a counter offer, use `/trade create` and select the same game. "
            "Tag the original trader as the target user.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Negotiate", style=discord.ButtonStyle.secondary, emoji="💬", custom_id="trade:negotiate", row=0)
    async def negotiate(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        modal = NegotiateModal(self.trade_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="View Details", style=discord.ButtonStyle.secondary, emoji="📋", custom_id="trade:details", row=1)
    async def view_details(self, interaction: discord.Interaction, button: Button):
        from utils.database import get_trade, get_user
        from ui.embeds import TradeEmbed, GAME_NAMES
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        requester_data = await get_user(trade['requester_id'])
        target_data = await get_user(trade['target_id']) if trade.get('target_id') else None
        
        items_str = trade.get('requester_items', '[]')
        items = json.loads(items_str) if items_str else []
        
        embed = discord.Embed(
            title=f"Trade #{self.trade_id} Details",
            color=0x3498DB
        )
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
        embed.add_field(name="Created", value=trade['created_at'][:10], inline=True)
        
        if requester_data:
            embed.add_field(
                name="Requester Trust",
                value=f"Score: {requester_data.get('trust_score', 50):.1f}/100\nTrades: {requester_data.get('total_trades', 0)}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="View Profile", style=discord.ButtonStyle.secondary, emoji="👤", custom_id="trade:profile", row=1)
    async def view_profile(self, interaction: discord.Interaction, button: Button):
        from utils.database import get_user
        
        other_id = self.target_id if interaction.user.id == self.requester_id else self.requester_id
        other_user = await interaction.client.fetch_user(other_id)
        user_data = await get_user(other_id)
        
        embed = discord.Embed(
            title=f"{other_user.display_name}'s Profile",
            color=0x9B59B6
        )
        embed.set_thumbnail(url=other_user.display_avatar.url)
        
        if user_data:
            trust_tier = user_data.get('trust_tier', 'Bronze')
            tier_emoji = {"Bronze": "🥉", "Silver": "🥈", "Gold": "🥇", "Platinum": "💎", "Diamond": "💠"}.get(trust_tier, "🏅")
            
            embed.add_field(name="Trust Score", value=f"{user_data.get('trust_score', 50):.1f}/100", inline=True)
            embed.add_field(name="Trust Tier", value=f"{tier_emoji} {trust_tier}", inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            
            embed.add_field(name="Total Trades", value=str(user_data.get('total_trades', 0)), inline=True)
            embed.add_field(name="Successful", value=str(user_data.get('successful_trades', 0)), inline=True)
            embed.add_field(name="Disputed", value=str(user_data.get('disputed_trades', 0)), inline=True)
            
            embed.add_field(name="Reliability", value=f"{user_data.get('reliability', 50):.0f}%", inline=True)
            embed.add_field(name="Fairness", value=f"{user_data.get('fairness', 50):.0f}%", inline=True)
            embed.add_field(name="Responsiveness", value=f"{user_data.get('responsiveness', 50):.0f}%", inline=True)
            
            if user_data.get('roblox_username'):
                embed.add_field(name="Roblox", value=user_data['roblox_username'], inline=True)
        else:
            embed.description = "This user hasn't made any trades yet."
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Message", style=discord.ButtonStyle.secondary, emoji="💌", custom_id="trade:message", row=1)
    async def message_trader(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        other_id = self.target_id if interaction.user.id == self.requester_id else self.requester_id
        other_user = await interaction.client.fetch_user(other_id)
        
        await interaction.response.send_message(
            f"Send a direct message to {other_user.mention} to discuss the trade!\n"
            f"**Tip:** Be respectful and clear about your expectations.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Share", style=discord.ButtonStyle.secondary, emoji="📤", custom_id="trade:share", row=1)
    async def share_trade(self, interaction: discord.Interaction, button: Button):
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
        
        share_text = (
            f"**Trade #{self.trade_id}** | {GAME_NAMES.get(trade['game'], trade['game'])}\n"
            f"Items: {items_preview}\n"
            f"Use `/trade view {self.trade_id}` to see details!"
        )
        
        await interaction.response.send_message(
            f"Share this trade info:\n```\n{share_text}\n```",
            ephemeral=True
        )
    
    @discord.ui.button(label="Bookmark", style=discord.ButtonStyle.secondary, emoji="🔖", custom_id="trade:bookmark", row=2)
    async def bookmark(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            f"Trade #{self.trade_id} bookmarked! Use `/trade view {self.trade_id}` to access it anytime.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Report", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="trade:report", row=2)
    async def report(self, interaction: discord.Interaction, button: Button):
        modal = ReportModal(self.trade_id, self.requester_id if interaction.user.id == self.target_id else self.target_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Help", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="trade:help", row=2)
    async def help_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="Trade Help Guide",
            color=0x3498DB,
            description="Here's how trading works:"
        )
        embed.add_field(
            name="1. Accept/Decline",
            value="The recipient can accept or decline the trade offer.",
            inline=False
        )
        embed.add_field(
            name="2. Counter Offer",
            value="Don't like the deal? Make a counter offer with different items.",
            inline=False
        )
        embed.add_field(
            name="3. Negotiate",
            value="Send a message to discuss terms before accepting.",
            inline=False
        )
        embed.add_field(
            name="4. In-Game Trade",
            value="Once accepted, both parties trade in the actual Roblox game.",
            inline=False
        )
        embed.add_field(
            name="5. Confirm",
            value="Both users confirm the trade was completed successfully.",
            inline=False
        )
        embed.add_field(
            name="Safety Tips",
            value="• Check the trader's trust score before trading\n"
                  "• Use screen recording for high-value trades\n"
                  "• Report any suspicious behavior immediately",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class PersistentHandoffView(View):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(timeout=None)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    @discord.ui.button(label="I Completed Trade", style=discord.ButtonStyle.success, emoji="✅", custom_id="handoff:confirm", row=0)
    async def confirm_trade(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        from utils.database import get_trade, update_trade, add_trade_history, get_user, update_user
        from utils.trust_engine import trust_engine
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        field = 'requester_confirmed' if interaction.user.id == self.requester_id else 'target_confirmed'
        await update_trade(self.trade_id, **{field: 1})
        
        trade = await get_trade(self.trade_id)
        
        if trade and trade['requester_confirmed'] and trade['target_confirmed']:
            from datetime import datetime
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
            
            for child in self.children:
                if hasattr(child, 'disabled'):
                    child.disabled = True
            if interaction.message:
                await interaction.message.edit(view=self)
            
            receipt_hash = trust_engine.generate_receipt_hash(trade) if trade else "N/A"
            await update_trade(self.trade_id, receipt_hash=receipt_hash)
            
            embed = discord.Embed(
                title="Trade Completed Successfully!",
                color=0x2ECC71,
                description=f"Trade #{self.trade_id} has been completed and verified."
            )
            embed.add_field(name="Receipt Hash", value=f"`{receipt_hash[:32]}...`", inline=False)
            embed.set_footer(text="Both parties have confirmed. Your trust scores have been updated!")
            
            await interaction.response.send_message(embed=embed)
        else:
            other_name = "the other trader" if interaction.user.id == self.requester_id else "the requester"
            await interaction.response.send_message(
                f"You've confirmed the trade! Waiting for {other_name} to confirm...",
                ephemeral=True
            )
    
    @discord.ui.button(label="Something Went Wrong", style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="handoff:issue", row=0)
    async def report_issue(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        from utils.database import update_trade, add_trade_history
        await update_trade(self.trade_id, status='disputed')
        await add_trade_history(self.trade_id, 'disputed', interaction.user.id)
        
        for child in self.children:
            if hasattr(child, 'disabled'):
                child.disabled = True
        if interaction.message:
            await interaction.message.edit(view=self)
        
        await interaction.response.send_message(
            "Trade has been marked as disputed. A moderator will review this case.\n"
            "Please provide any screenshots or evidence using `/report`.",
            ephemeral=False
        )
    
    @discord.ui.button(label="Upload Proof", style=discord.ButtonStyle.secondary, emoji="📸", custom_id="handoff:proof", row=0)
    async def upload_proof(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            "**How to Upload Proof:**\n"
            "1. Take a screenshot of the completed in-game trade\n"
            "2. Reply to this message with the image attached\n"
            "3. Your proof will be stored for verification\n\n"
            "*Having proof helps protect you in case of disputes!*",
            ephemeral=True
        )
    
    @discord.ui.button(label="Cancel Trade", style=discord.ButtonStyle.secondary, emoji="🚫", custom_id="handoff:cancel", row=1)
    async def cancel_trade(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        view = ConfirmCancelView(self.trade_id, interaction.user.id)
        await interaction.response.send_message(
            "Are you sure you want to cancel this trade? This action cannot be undone.",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Extend Time", style=discord.ButtonStyle.secondary, emoji="⏰", custom_id="handoff:extend", row=1)
    async def extend_time(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            "Trade time has been extended by 15 minutes. "
            "Take your time to complete the in-game trade safely!",
            ephemeral=True
        )
    
    @discord.ui.button(label="Trading Tips", style=discord.ButtonStyle.secondary, emoji="💡", custom_id="handoff:tips", row=1)
    async def trading_tips(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="In-Game Trading Tips",
            color=0xF39C12
        )
        embed.add_field(
            name="Before Trading",
            value="• Double-check the items in the trade window\n"
                  "• Make sure quantities match what was agreed\n"
                  "• Verify you're trading with the right person",
            inline=False
        )
        embed.add_field(
            name="During Trade",
            value="• Take a screenshot before confirming\n"
                  "• Don't rush - scammers try to pressure you\n"
                  "• If anything seems off, decline and report",
            inline=False
        )
        embed.add_field(
            name="After Trade",
            value="• Confirm completion using the button above\n"
                  "• Keep your proof screenshots for 7 days\n"
                  "• Leave feedback for the other trader",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfirmCancelView(View):
    def __init__(self, trade_id: int, user_id: int):
        super().__init__(timeout=60)
        self.trade_id = trade_id
        self.user_id = user_id
    
    @discord.ui.button(label="Yes, Cancel Trade", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you.", ephemeral=True)
            return
        
        from utils.database import update_trade, add_trade_history
        await update_trade(self.trade_id, status='cancelled')
        await add_trade_history(self.trade_id, 'cancelled', interaction.user.id)
        
        await interaction.response.send_message("Trade has been cancelled.", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="No, Keep Trading", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_action(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you.", ephemeral=True)
            return
        
        await interaction.response.send_message("Cancelled. Continue with your trade!", ephemeral=True)
        self.stop()


class NegotiateModal(Modal, title="Negotiate Trade"):
    message = TextInput(
        label="Your Message",
        placeholder="What would you like to discuss about this trade?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
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
        
        embed = discord.Embed(
            title=f"Negotiation for Trade #{self.trade_id}",
            color=0x3498DB,
            description=self.message.value
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="Reply using the Negotiate button")
        
        await interaction.response.send_message(
            f"{other_user.mention}",
            embed=embed
        )


class ReportModal(Modal, title="Report User"):
    reason = TextInput(
        label="Reason for Report",
        placeholder="Describe what happened (e.g., scam attempt, harassment)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    evidence = TextInput(
        label="Evidence (Optional)",
        placeholder="Links to screenshots or video proof",
        style=discord.TextStyle.short,
        required=False,
        max_length=500
    )
    
    def __init__(self, trade_id: int, reported_id: int):
        super().__init__()
        self.trade_id = trade_id
        self.reported_id = reported_id
    
    async def on_submit(self, interaction: discord.Interaction):
        from utils.database import log_audit
        
        await log_audit(
            'user_reported',
            interaction.user.id,
            self.reported_id,
            f"Trade {self.trade_id}: {self.reason.value}"
        )
        
        embed = discord.Embed(
            title="Report Submitted",
            color=0xE74C3C,
            description="Your report has been submitted and will be reviewed by moderators."
        )
        embed.add_field(name="Trade ID", value=str(self.trade_id), inline=True)
        embed.add_field(name="Status", value="Pending Review", inline=True)
        embed.set_footer(text="Thank you for helping keep our community safe!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TradeAnnouncementView(View):
    def __init__(self, trade_id: int, requester_id: int, game: str):
        super().__init__(timeout=None)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.game = game
    
    @discord.ui.button(label="I'm Interested!", style=discord.ButtonStyle.success, emoji="🙋", custom_id="announce:interested", row=0)
    async def interested(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.requester_id:
            await interaction.response.send_message("You can't express interest in your own trade!", ephemeral=True)
            return
        
        requester = await interaction.client.fetch_user(self.requester_id)
        
        embed = discord.Embed(
            title="Someone is Interested!",
            color=0x2ECC71,
            description=f"{interaction.user.mention} is interested in your Trade #{self.trade_id}!"
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Next Step", value=f"Use `/trade create` targeting {interaction.user.mention} to send them a formal offer!", inline=False)
        
        try:
            await requester.send(embed=embed)
            await interaction.response.send_message(
                f"Your interest has been sent to {requester.display_name}! They'll reach out to you soon.",
                ephemeral=True
            )
        except:
            await interaction.response.send_message(
                f"Couldn't DM the trader. Mention them here: {requester.mention}",
                ephemeral=True
            )
    
    @discord.ui.button(label="View Items", style=discord.ButtonStyle.secondary, emoji="📦", custom_id="announce:items", row=0)
    async def view_items(self, interaction: discord.Interaction, button: Button):
        from utils.database import get_trade
        from ui.embeds import GAME_NAMES
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        items_str = trade.get('requester_items', '[]')
        items = json.loads(items_str) if items_str else []
        
        embed = discord.Embed(
            title=f"Items in Trade #{self.trade_id}",
            color=0x9B59B6
        )
        embed.add_field(name="Game", value=GAME_NAMES.get(trade['game'], trade['game']), inline=True)
        
        if items:
            for i, item in enumerate(items[:25], 1):
                rarity = item.get('rarity', 'Common')
                value = item.get('value', 0)
                rarity_emoji = {"Common": "⚪", "Uncommon": "🟢", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡", "Mythic": "🔴"}.get(rarity, "⚪")
                embed.add_field(
                    name=f"{rarity_emoji} {item['name']}",
                    value=f"Rarity: {rarity}\nValue: {value:,}",
                    inline=True
                )
        else:
            embed.description = "No items found in this trade."
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Trader Profile", style=discord.ButtonStyle.secondary, emoji="👤", custom_id="announce:profile", row=0)
    async def trader_profile(self, interaction: discord.Interaction, button: Button):
        from utils.database import get_user
        
        user = await interaction.client.fetch_user(self.requester_id)
        user_data = await get_user(self.requester_id)
        
        embed = discord.Embed(
            title=f"{user.display_name}'s Trading Profile",
            color=0x3498DB
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        if user_data:
            trust_tier = user_data.get('trust_tier', 'Bronze')
            tier_emoji = {"Bronze": "🥉", "Silver": "🥈", "Gold": "🥇", "Platinum": "💎", "Diamond": "💠"}.get(trust_tier, "🏅")
            
            embed.add_field(name="Trust Score", value=f"{user_data.get('trust_score', 50):.1f}/100", inline=True)
            embed.add_field(name="Trust Tier", value=f"{tier_emoji} {trust_tier}", inline=True)
            embed.add_field(name="Total Trades", value=str(user_data.get('total_trades', 0)), inline=True)
            embed.add_field(name="Successful", value=str(user_data.get('successful_trades', 0)), inline=True)
            embed.add_field(name="Disputed", value=str(user_data.get('disputed_trades', 0)), inline=True)
            
            success_rate = 0
            if user_data.get('total_trades', 0) > 0:
                success_rate = (user_data.get('successful_trades', 0) / user_data.get('total_trades', 1)) * 100
            embed.add_field(name="Success Rate", value=f"{success_rate:.1f}%", inline=True)
        else:
            embed.description = "This is a new trader with no history yet."
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Share", style=discord.ButtonStyle.secondary, emoji="📤", custom_id="announce:share", row=1)
    async def share(self, interaction: discord.Interaction, button: Button):
        from utils.database import get_trade
        from ui.embeds import GAME_NAMES
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        user = await interaction.client.fetch_user(self.requester_id)
        
        items_str = trade.get('requester_items', '[]')
        items = json.loads(items_str) if items_str else []
        items_preview = ", ".join([i['name'] for i in items[:3]])
        if len(items) > 3:
            items_preview += f" +{len(items) - 3} more"
        
        share_text = (
            f"Check out this trade from {user.display_name}!\n"
            f"Game: {GAME_NAMES.get(trade['game'], trade['game'])}\n"
            f"Items: {items_preview}\n"
            f"Trade ID: #{self.trade_id}"
        )
        
        await interaction.response.send_message(
            f"Share this:\n```\n{share_text}\n```",
            ephemeral=True
        )
    
    @discord.ui.button(label="Report", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="announce:report", row=1)
    async def report(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.requester_id:
            await interaction.response.send_message("You can't report your own trade!", ephemeral=True)
            return
        
        modal = ReportModal(self.trade_id, self.requester_id)
        await interaction.response.send_modal(modal)


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
        await interaction.response.send_message("Trade accepted! Proceeding to trust check...", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        self.result = 'declined'
        await interaction.response.send_message("Trade declined.", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="Counter Offer", style=discord.ButtonStyle.primary, emoji="🔄")
    async def counter(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("Only the trade recipient can counter.", ephemeral=True)
            return
        
        self.result = 'counter'
        await interaction.response.send_message("Please use `/trade create` to make a counter offer.", ephemeral=True)
        self.stop()
    
    async def on_timeout(self):
        self.result = 'expired'
        if self.message:
            try:
                await self.message.edit(content="This trade offer has expired.", view=None)
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
            await interaction.response.send_message("You've confirmed the in-game trade. Waiting for the other party...", ephemeral=True)
        elif interaction.user.id == self.target_id:
            self.target_confirmed = True
            await interaction.response.send_message("You've confirmed the in-game trade. Waiting for the other party...", ephemeral=True)
        else:
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        if self.requester_confirmed and self.target_confirmed:
            self.result = 'completed'
            self.stop()
    
    @discord.ui.button(label="Something went wrong", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def report_issue(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        self.result = 'disputed'
        await interaction.response.send_message("Trade marked as disputed. A moderator will review.", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="Upload Proof", style=discord.ButtonStyle.secondary, emoji="📷")
    async def upload_proof(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            "Please reply to this message with a screenshot of the completed trade.\n"
            "Your proof will be stored for verification.",
            ephemeral=True
        )


class ConfirmView(View):
    def __init__(self, user_id: int, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.result: Optional[bool] = None
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you.", ephemeral=True)
            return
        
        self.result = True
        await interaction.response.defer()
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you.", ephemeral=True)
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
            await interaction.response.send_message("This is not for you.", ephemeral=True)
            return
        
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you.", ephemeral=True)
            return
        
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you.", ephemeral=True)
            return
        
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you.", ephemeral=True)
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
            await interaction.response.send_message("This is not for you.", ephemeral=True)
            return
        
        self.selected_game = select.values[0]
        await interaction.response.defer()
        self.stop()
    
    async def on_timeout(self):
        self.selected_game = None
