import discord
from discord.ui import Modal, TextInput
from typing import Optional

class TradeModal(Modal, title="Create Trade Offer"):
    items = TextInput(
        label="Items to Trade",
        placeholder="Enter items separated by commas (e.g., Huge Cat, Big Dog)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    requesting = TextInput(
        label="Items You Want (Optional)",
        placeholder="Enter items you're looking for, or leave blank for offers",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000
    )
    
    notes = TextInput(
        label="Notes (Optional)",
        placeholder="Any additional information about the trade",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )
    
    def __init__(self, game: str):
        super().__init__()
        self.game = game
        self.trade_data: Optional[dict] = None
    
    async def on_submit(self, interaction: discord.Interaction):
        self.trade_data = {
            'game': self.game,
            'offering': [item.strip() for item in self.items.value.split(',') if item.strip()],
            'requesting': [item.strip() for item in self.requesting.value.split(',') if item.strip()] if self.requesting.value else [],
            'notes': self.notes.value.strip() if self.notes.value else None
        }
        await interaction.response.defer()


class ReportModal(Modal, title="Report User"):
    reason = TextInput(
        label="Reason for Report",
        placeholder="Describe what happened...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    evidence = TextInput(
        label="Evidence (Optional)",
        placeholder="Links to screenshots or other evidence",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )
    
    trade_id = TextInput(
        label="Trade ID (Optional)",
        placeholder="If this is related to a specific trade",
        style=discord.TextStyle.short,
        required=False,
        max_length=20
    )
    
    def __init__(self, reported_user_id: int):
        super().__init__()
        self.reported_user_id = reported_user_id
        self.report_data: Optional[dict] = None
    
    async def on_submit(self, interaction: discord.Interaction):
        self.report_data = {
            'reported_id': self.reported_user_id,
            'reason': self.reason.value.strip(),
            'evidence': self.evidence.value.strip() if self.evidence.value else None,
            'trade_id': int(self.trade_id.value) if self.trade_id.value and self.trade_id.value.isdigit() else None
        }
        await interaction.response.send_message("Report submitted. A moderator will review it.", ephemeral=True)


class ProofModal(Modal, title="Submit Trade Proof"):
    proof_url = TextInput(
        label="Screenshot URL",
        placeholder="Paste a link to your screenshot...",
        style=discord.TextStyle.short,
        required=True,
        max_length=500
    )
    
    description = TextInput(
        label="Description",
        placeholder="Briefly describe what the screenshot shows",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=300
    )
    
    def __init__(self, trade_id: int):
        super().__init__()
        self.trade_id = trade_id
        self.proof_data: Optional[dict] = None
    
    async def on_submit(self, interaction: discord.Interaction):
        self.proof_data = {
            'trade_id': self.trade_id,
            'url': self.proof_url.value.strip(),
            'description': self.description.value.strip() if self.description.value else None
        }
        await interaction.response.send_message("Proof submitted successfully.", ephemeral=True)


class InventoryAddModal(Modal, title="Add Item to Inventory"):
    item_name = TextInput(
        label="Item Name",
        placeholder="Enter the exact item name",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )
    
    quantity = TextInput(
        label="Quantity",
        placeholder="1",
        style=discord.TextStyle.short,
        required=False,
        max_length=5,
        default="1"
    )
    
    for_trade = TextInput(
        label="Available for Trade? (yes/no)",
        placeholder="yes",
        style=discord.TextStyle.short,
        required=False,
        max_length=5,
        default="yes"
    )
    
    def __init__(self, game: str):
        super().__init__()
        self.game = game
        self.item_data: Optional[dict] = None
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity.value) if self.quantity.value else 1
        except ValueError:
            qty = 1
        
        self.item_data = {
            'game': self.game,
            'name': self.item_name.value.strip(),
            'quantity': max(1, qty),
            'for_trade': self.for_trade.value.lower() in ('yes', 'y', 'true', '1')
        }
        await interaction.response.defer()


class LinkRobloxModal(Modal, title="Link Roblox Account"):
    username = TextInput(
        label="Roblox Username",
        placeholder="Enter your Roblox username",
        style=discord.TextStyle.short,
        required=True,
        max_length=20
    )
    
    def __init__(self):
        super().__init__()
        self.username_value: Optional[str] = None
    
    async def on_submit(self, interaction: discord.Interaction):
        self.username_value = self.username.value.strip()
        await interaction.response.defer()
