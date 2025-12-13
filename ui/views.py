import discord
from discord.ui import View, Button, Select
from typing import Optional, Callable, List, Dict, Any
import asyncio

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
