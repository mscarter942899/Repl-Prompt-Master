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
        
        from utils.database import update_trade, add_trade_history, get_trade, create_trade_ticket
        from ui.embeds import GAME_NAMES
        
        await update_trade(self.trade_id, status='accepted')
        await add_trade_history(self.trade_id, 'accepted', interaction.user.id)
        
        if self.view:
            for child in self.view.children:
                if hasattr(child, 'disabled'):
                    child.disabled = True
            if interaction.message:
                await interaction.message.edit(view=self.view)
        
        trade = await get_trade(self.trade_id)
        game_name = GAME_NAMES.get(trade['game'], trade['game']) if trade else "Unknown Game"
        requester = await interaction.client.fetch_user(self.requester_id)
        
        if interaction.guild and interaction.channel and isinstance(interaction.channel, discord.TextChannel):
            try:
                thread = await interaction.channel.create_thread(
                    name=f"Trade #{self.trade_id} - {requester.display_name} & {interaction.user.display_name}",
                    type=discord.ChannelType.private_thread,
                    auto_archive_duration=1440
                )
                
                try:
                    await thread.add_user(requester)
                except (discord.Forbidden, discord.HTTPException):
                    pass
                try:
                    await thread.add_user(interaction.user)
                except (discord.Forbidden, discord.HTTPException):
                    pass
                
                await create_trade_ticket(
                    trade_id=self.trade_id,
                    thread_id=thread.id,
                    channel_id=interaction.channel.id,
                    guild_id=interaction.guild.id,
                    requester_id=self.requester_id,
                    target_id=self.target_id
                )
                
                welcome_embed = discord.Embed(
                    title=f"🎫 Trade Ticket #{self.trade_id}",
                    description=f"**{game_name}** trade between {requester.mention} and {interaction.user.mention}",
                    color=0x2ECC71
                )
                welcome_embed.add_field(
                    name="📋 How This Works",
                    value="1️⃣ Share your Roblox usernames below\n"
                          "2️⃣ Add each other in-game\n"
                          "3️⃣ Complete the trade in Roblox\n"
                          "4️⃣ Both confirm using the buttons",
                    inline=False
                )
                welcome_embed.add_field(
                    name="⚠️ Safety Reminders",
                    value="• Never trade items outside the agreed deal\n"
                          "• Take screenshots of the trade\n"
                          "• Report any issues immediately",
                    inline=False
                )
                welcome_embed.set_footer(text="This ticket will auto-archive after 24 hours of inactivity")
                
                ticket_view = TradeTicketView(self.trade_id, self.requester_id, self.target_id, trade['game'] if trade else 'unknown')
                
                await thread.send(
                    f"🔔 {requester.mention} {interaction.user.mention} - Your private trade room is ready!",
                    embed=welcome_embed,
                    view=ticket_view
                )
                
                await interaction.response.send_message(
                    f"✅ Trade accepted! A private trade ticket has been created: {thread.mention}",
                    ephemeral=False
                )
                
            except discord.Forbidden:
                await interaction.response.send_message(
                    "Trade accepted, but I couldn't create a private thread. Please coordinate in DMs.",
                    ephemeral=False
                )
                handoff_view = DynamicHandoffView(self.trade_id, self.requester_id, self.target_id)
                await interaction.followup.send(
                    f"{requester.mention} {interaction.user.mention} - Complete your trade in-game!",
                    view=handoff_view
                )
        else:
            await interaction.response.send_message("Trade accepted! Complete the trade in-game and confirm below.", ephemeral=False)
            handoff_view = DynamicHandoffView(self.trade_id, self.requester_id, self.target_id)
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
        
        from utils.database import get_trade
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        modal = CounterOfferModal(self.trade_id, trade['game'], trade['requester_id'])
        await interaction.response.send_modal(modal)


class CounterOfferModal(Modal):
    def __init__(self, trade_id: int, game: str, requester_id: int):
        super().__init__(title="Make Counter Offer")
        self.trade_id = trade_id
        self.game = game
        self.requester_id = requester_id
        
        self.offering_items = TextInput(
            label="Items You'll Give",
            placeholder="Enter items separated by commas...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.offering_items)
        
        self.requesting_items = TextInput(
            label="Items You Want",
            placeholder="Enter items you want, separated by commas...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.requesting_items)
        
        if game == 'ps99':
            self.gems = TextInput(
                label="Diamonds to Add (Optional)",
                placeholder="e.g., 500M, 1B, 2.5T",
                style=discord.TextStyle.short,
                required=False,
                max_length=20
            )
            self.add_item(self.gems)
        
        self.notes = TextInput(
            label="Notes",
            placeholder="Any additional notes for your counter...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=200
        )
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        from utils.database import get_trade, update_trade, add_trade_history
        from ui.embeds import GAME_NAMES
        from ui.trade_builder import parse_gem_value, format_value
        
        offering = [i.strip() for i in self.offering_items.value.split(',') if i.strip()]
        requesting = [i.strip() for i in self.requesting_items.value.split(',') if i.strip()] if self.requesting_items.value else []
        
        gems = 0
        if hasattr(self, 'gems') and self.gems.value:
            gems = parse_gem_value(self.gems.value)
        
        counter_data = {
            'offering': offering,
            'requesting': requesting,
            'gems': gems,
            'notes': self.notes.value if self.notes.value else '',
            'from_user': interaction.user.id
        }
        
        await update_trade(self.trade_id, counter_offer_data=json.dumps(counter_data), status='counter_offered')
        await add_trade_history(self.trade_id, 'counter_offered', interaction.user.id)
        
        requester = await interaction.client.fetch_user(self.requester_id)
        
        embed = discord.Embed(
            title="🔄 Counter Offer Received!",
            description=f"{interaction.user.mention} has made a counter offer for Trade #{self.trade_id}",
            color=0x3498DB
        )
        embed.add_field(name="Game", value=GAME_NAMES.get(self.game, self.game), inline=True)
        
        if offering:
            embed.add_field(name="📦 They Offer", value="\n".join([f"• {i}" for i in offering[:5]]), inline=True)
        if requesting:
            embed.add_field(name="🎯 They Want", value="\n".join([f"• {i}" for i in requesting[:5]]), inline=True)
        if gems > 0:
            embed.add_field(name="💎 Diamonds", value=format_value(gems), inline=True)
        if counter_data['notes']:
            embed.add_field(name="📝 Notes", value=counter_data['notes'][:100], inline=False)
        
        counter_view = CounterOfferResponseView(self.trade_id, self.requester_id, interaction.user.id)
        
        await interaction.response.send_message(
            content=f"{requester.mention} - You have a counter offer!",
            embed=embed,
            view=counter_view
        )


class CounterOfferResponseView(View):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(timeout=None)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
        
        self.add_item(AcceptCounterButton(trade_id, requester_id, target_id))
        self.add_item(DeclineCounterButton(trade_id, requester_id, target_id))
        self.add_item(CounterAgainButton(trade_id, requester_id))


class AcceptCounterButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Accept Counter", style=discord.ButtonStyle.success, emoji="✅", custom_id=f"counter:accept:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("Only the original trader can accept this counter.", ephemeral=True)
            return
        
        from utils.database import update_trade, add_trade_history
        
        await update_trade(self.trade_id, status='accepted')
        await add_trade_history(self.trade_id, 'counter_accepted', interaction.user.id)
        
        if self.view:
            for child in self.view.children:
                if hasattr(child, 'disabled'):
                    child.disabled = True
            if interaction.message:
                await interaction.message.edit(view=self.view)
        
        target = await interaction.client.fetch_user(self.target_id)
        
        await interaction.response.send_message(
            f"✅ Counter offer accepted! {interaction.user.mention} and {target.mention} - proceed to complete the trade in-game!",
            view=DynamicHandoffView(self.trade_id, self.requester_id, self.target_id)
        )


class DeclineCounterButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Decline", style=discord.ButtonStyle.danger, emoji="❌", custom_id=f"counter:decline:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("Only the original trader can decline.", ephemeral=True)
            return
        
        from utils.database import update_trade, add_trade_history
        
        await update_trade(self.trade_id, status='pending', counter_offer_data=None)
        await add_trade_history(self.trade_id, 'counter_declined', interaction.user.id)
        
        if self.view:
            for child in self.view.children:
                if hasattr(child, 'disabled'):
                    child.disabled = True
            if interaction.message:
                await interaction.message.edit(view=self.view)
        
        await interaction.response.send_message("Counter offer declined. Trade returned to pending.")


class CounterAgainButton(Button):
    def __init__(self, trade_id: int, requester_id: int):
        super().__init__(label="Counter Back", style=discord.ButtonStyle.primary, emoji="🔄", custom_id=f"counter:again:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("Only the original trader can counter.", ephemeral=True)
            return
        
        from utils.database import get_trade
        
        trade = await get_trade(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        modal = CounterOfferModal(self.trade_id, trade['game'], trade['target_id'])
        await interaction.response.send_modal(modal)


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


class TradeTicketView(View):
    """Enhanced view for trade tickets with all the tools traders need."""
    def __init__(self, trade_id: int, requester_id: int, target_id: int, game: str):
        super().__init__(timeout=None)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
        self.game = game
        
        self.add_item(ShareRobloxUsernameButton(trade_id, requester_id, target_id))
        self.add_item(TicketConfirmTradeButton(trade_id, requester_id, target_id))
        self.add_item(SafetyChecklistButton(trade_id))
        self.add_item(ViewTradeItemsButton(trade_id))
        self.add_item(TicketUploadProofButton(trade_id, requester_id, target_id))
        self.add_item(InviteModeratorButton(trade_id, requester_id, target_id))
        self.add_item(TicketReportIssueButton(trade_id, requester_id, target_id))
        self.add_item(CloseTicketButton(trade_id, requester_id, target_id))


class ShareRobloxUsernameButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Share Roblox Username", style=discord.ButtonStyle.primary, emoji="🎮", custom_id=f"ticket:roblox:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        modal = RobloxUsernameModal(self.trade_id)
        await interaction.response.send_modal(modal)


class RobloxUsernameModal(Modal):
    def __init__(self, trade_id: int):
        super().__init__(title="Share Your Roblox Username")
        self.trade_id = trade_id
        self.username_input = TextInput(
            label="Your Roblox Username",
            placeholder="Enter your exact Roblox username...",
            min_length=3,
            max_length=20,
            required=True
        )
        self.add_item(self.username_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        username = self.username_input.value
        embed = discord.Embed(
            title="🎮 Roblox Username Shared",
            description=f"**{interaction.user.display_name}**'s Roblox username:",
            color=0x00A2FF
        )
        embed.add_field(name="Username", value=f"`{username}`", inline=False)
        embed.add_field(name="Profile Link", value=f"[View Profile](https://www.roblox.com/users/profile?username={username})", inline=False)
        embed.set_footer(text="Add them in-game to start the trade!")
        
        await interaction.response.send_message(embed=embed)


class TicketConfirmTradeButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Confirm Trade Complete", style=discord.ButtonStyle.success, emoji="✅", custom_id=f"ticket:confirm:{trade_id}", row=0)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        from utils.database import get_trade, update_trade, add_trade_history, get_user, update_user, close_trade_ticket
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
            await close_trade_ticket(self.trade_id)
            
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
            
            embed = discord.Embed(
                title="🎉 Trade Completed Successfully!",
                description=f"Trade #{self.trade_id} has been verified and completed.",
                color=0x2ECC71
            )
            embed.add_field(name="Receipt Hash", value=f"`{receipt_hash[:32]}...`", inline=False)
            embed.add_field(name="Status", value="Both parties confirmed", inline=True)
            embed.set_footer(text="Trust scores updated! This ticket will be archived.")
            
            await interaction.response.send_message(embed=embed)
            
            if isinstance(interaction.channel, discord.Thread):
                await interaction.followup.send("🔒 This ticket will be archived in 1 minute. Thank you for trading safely!")
                import asyncio
                await asyncio.sleep(60)
                try:
                    await interaction.channel.edit(archived=True, locked=True)
                except:
                    pass
        else:
            other_user = await interaction.client.fetch_user(self.target_id if interaction.user.id == self.requester_id else self.requester_id)
            await interaction.response.send_message(
                f"✅ {interaction.user.display_name} confirmed the trade!\n⏳ Waiting for {other_user.display_name} to confirm...",
                ephemeral=False
            )


class SafetyChecklistButton(Button):
    def __init__(self, trade_id: int):
        super().__init__(label="Safety Checklist", style=discord.ButtonStyle.secondary, emoji="🛡️", custom_id=f"ticket:safety:{trade_id}", row=1)
        self.trade_id = trade_id
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ Trade Safety Checklist",
            description="Make sure you follow these steps for a safe trade:",
            color=0xF1C40F
        )
        embed.add_field(
            name="Before Trading",
            value="☐ Verified the other player's username\n"
                  "☐ Double-checked the items being traded\n"
                  "☐ Confirmed the agreed values\n"
                  "☐ Screenshots ready to record the trade",
            inline=False
        )
        embed.add_field(
            name="During Trade",
            value="☐ In the same Roblox server\n"
                  "☐ Items in trade window match agreement\n"
                  "☐ No additional items requested\n"
                  "☐ Take a screenshot before accepting",
            inline=False
        )
        embed.add_field(
            name="After Trading",
            value="☐ Received the correct items\n"
                  "☐ Upload proof if needed\n"
                  "☐ Confirm trade in Discord\n"
                  "☐ Report any issues immediately",
            inline=False
        )
        embed.set_footer(text="Stay safe and report scammers!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ViewTradeItemsButton(Button):
    def __init__(self, trade_id: int):
        super().__init__(label="View Trade Items", style=discord.ButtonStyle.secondary, emoji="📦", custom_id=f"ticket:items:{trade_id}", row=1)
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
        
        embed = discord.Embed(
            title=f"📦 Trade #{self.trade_id} Items",
            description=f"**Game:** {GAME_NAMES.get(trade['game'], trade['game'])}",
            color=0x3498DB
        )
        
        if items:
            for i, item in enumerate(items[:10], 1):
                rarity = item.get('rarity', 'Common')
                value = item.get('value', 0)
                rarity_emoji = {"Common": "⚪", "Uncommon": "🟢", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡", "Mythical": "🔴"}.get(rarity, "⚪")
                embed.add_field(
                    name=f"{rarity_emoji} {item['name']}",
                    value=f"Value: {value:,.0f} | {rarity}",
                    inline=True
                )
            if len(items) > 10:
                embed.add_field(name="...", value=f"and {len(items) - 10} more items", inline=False)
        
        total_value = sum(i.get('value', 0) for i in items)
        embed.add_field(name="💰 Total Value", value=f"{total_value:,.0f}", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TicketUploadProofButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Upload Proof", style=discord.ButtonStyle.secondary, emoji="📸", custom_id=f"ticket:proof:{trade_id}", row=1)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📸 Upload Trade Proof",
            description="To upload proof of your trade:",
            color=0x3498DB
        )
        embed.add_field(
            name="Instructions",
            value="1. Take a screenshot of the completed trade\n"
                  "2. Reply to this message with your screenshot attached\n"
                  "3. The image will be saved as proof for this trade",
            inline=False
        )
        embed.set_footer(text="Screenshots help resolve disputes if issues arise")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class InviteModeratorButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Invite Mod", style=discord.ButtonStyle.secondary, emoji="👮", custom_id=f"ticket:invitemod:{trade_id}", row=2)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return
        
        from utils.database import get_guild_settings
        
        if not interaction.guild:
            await interaction.response.send_message("This feature only works in a server.", ephemeral=True)
            return
        
        settings = await get_guild_settings(interaction.guild.id)
        mod_role_id = settings.get('mod_role_id') if settings else None
        
        if mod_role_id:
            mod_role = interaction.guild.get_role(mod_role_id)
            if mod_role:
                await interaction.response.send_message(
                    f"🚨 {mod_role.mention} - A moderator has been requested for Trade #{self.trade_id}!\n"
                    f"Requested by: {interaction.user.mention}",
                    allowed_mentions=discord.AllowedMentions(roles=True)
                )
            else:
                await interaction.response.send_message(
                    "⚠️ Moderator role not found. Please contact server staff directly.",
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "⚠️ No moderator role configured. Please contact server staff directly.\n"
                "**Tip:** Admins can set a mod role with `/settings modrole`",
                ephemeral=True
            )


class TicketReportIssueButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Report Issue", style=discord.ButtonStyle.danger, emoji="⚠️", custom_id=f"ticket:issue:{trade_id}", row=2)
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
        
        embed = discord.Embed(
            title="⚠️ Trade Issue Reported",
            description=f"Trade #{self.trade_id} has been flagged for review.",
            color=0xE74C3C
        )
        embed.add_field(name="Reported by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Status", value="Awaiting moderator review", inline=True)
        embed.add_field(
            name="What happens now?",
            value="• A moderator will review this trade\n"
                  "• Both parties should provide evidence\n"
                  "• Do not delete any messages in this ticket",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)


class CloseTicketButton(Button):
    def __init__(self, trade_id: int, requester_id: int, target_id: int):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id=f"ticket:close:{trade_id}", row=2)
        self.trade_id = trade_id
        self.requester_id = requester_id
        self.target_id = target_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.requester_id, self.target_id):
            if not (interaction.guild and isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_threads):
                await interaction.response.send_message("Only trade participants or moderators can close this ticket.", ephemeral=True)
                return
        
        from utils.database import get_trade, close_trade_ticket
        
        trade = await get_trade(self.trade_id)
        if trade and trade['status'] not in ('completed', 'cancelled', 'disputed'):
            view = ConfirmCloseView(self.trade_id, interaction.user.id)
            await interaction.response.send_message(
                "⚠️ This trade is not yet complete. Are you sure you want to close the ticket?",
                view=view,
                ephemeral=True
            )
        else:
            await close_trade_ticket(self.trade_id)
            
            if self.view:
                for child in self.view.children:
                    if hasattr(child, 'disabled'):
                        child.disabled = True
                if interaction.message:
                    await interaction.message.edit(view=self.view)
            
            await interaction.response.send_message("🔒 Ticket closed. This thread will be archived.")
            
            if isinstance(interaction.channel, discord.Thread):
                import asyncio
                await asyncio.sleep(5)
                try:
                    await interaction.channel.edit(archived=True)
                except:
                    pass


class ConfirmCloseView(View):
    def __init__(self, trade_id: int, user_id: int):
        super().__init__(timeout=60)
        self.trade_id = trade_id
        self.user_id = user_id
    
    @discord.ui.button(label="Yes, Close", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        
        from utils.database import update_trade, close_trade_ticket
        
        await update_trade(self.trade_id, status='cancelled')
        await close_trade_ticket(self.trade_id)
        
        await interaction.response.send_message("🔒 Ticket closed and trade cancelled.")
        
        if isinstance(interaction.channel, discord.Thread):
            import asyncio
            await asyncio.sleep(5)
            try:
                await interaction.channel.edit(archived=True)
            except:
                pass
        
        self.stop()
    
    @discord.ui.button(label="No, Keep Open", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            return
        await interaction.response.send_message("Ticket will remain open.", ephemeral=True)
        self.stop()


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
