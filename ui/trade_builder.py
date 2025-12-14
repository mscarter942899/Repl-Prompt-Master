import discord
from discord.ui import View, Button, Select, Modal, TextInput
from typing import Optional, List, Dict, Any
import json


RARITY_EMOJIS = {
    'Common': '⚪',
    'Uncommon': '🟢',
    'Rare': '🔵',
    'Epic': '🟣',
    'Legendary': '🟡',
    'Mythic': '🔴',
    'Titanic': '⭐',
    'Huge': '💫',
    'Divine': '✨',
    'Secret': '🔮',
    'Mythical': '🌟',
    'Ultra Rare': '💎',
    'Exclusive': '🎭',
    'Event': '🎃',
    'Limited': '🏆'
}

RARITY_COLORS = {
    'Common': 0x9E9E9E,
    'Uncommon': 0x4CAF50,
    'Rare': 0x2196F3,
    'Epic': 0x9C27B0,
    'Legendary': 0xFFC107,
    'Mythic': 0xF44336,
    'Titanic': 0xE91E63,
    'Huge': 0x673AB7,
    'Divine': 0x00BCD4,
    'Secret': 0x7C4DFF
}


def format_value(value: float) -> str:
    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.2f}K"
    else:
        return f"{value:,.0f}"


def parse_gem_value(text: str) -> int:
    text = text.strip().upper().replace(',', '').replace(' ', '')
    multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000, 'T': 1_000_000_000_000}
    
    for suffix, mult in multipliers.items():
        if text.endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return 0
    
    try:
        return int(float(text))
    except ValueError:
        return 0


class TradeBuilderView(View):
    def __init__(self, user_id: int, game: str, target_id: Optional[int] = None):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.game = game
        self.target_id = target_id
        self.offering_items: List[Dict] = []
        self.requesting_items: List[Dict] = []
        self.offering_gems: int = 0
        self.requesting_gems: int = 0
        self.notes: str = ""
        self.completed = False
        self.cancelled = False
        
        self._build_view()
    
    def _build_view(self):
        self.clear_items()
        
        self.add_item(AddOfferingItemButton())
        self.add_item(AddRequestingItemButton())
        
        if self.game == 'ps99':
            self.add_item(SetOfferingGemsButton())
            self.add_item(SetRequestingGemsButton())
        
        self.add_item(AddNotesButton())
        self.add_item(PreviewTradeButton())
        self.add_item(ConfirmTradeButton())
        self.add_item(CancelTradeButton())
    
    def get_summary_embed(self) -> discord.Embed:
        from ui.embeds import GAME_NAMES, GAME_COLORS
        
        color = GAME_COLORS.get(self.game, 0x7289DA)
        embed = discord.Embed(
            title=f"🔨 Trade Builder - {GAME_NAMES.get(self.game, self.game.upper())}",
            description="Use the buttons below to build your trade offer!",
            color=color
        )
        
        offering_lines = []
        offering_total = 0
        for item in self.offering_items:
            emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
            value = item.get('value', 0)
            offering_total += value
            line = f"{emoji} **{item['name']}**"
            if value > 0:
                line += f" ({format_value(value)})"
            offering_lines.append(line)
        
        if self.game == 'ps99' and self.offering_gems > 0:
            offering_lines.append(f"💎 **{format_value(self.offering_gems)} Diamonds**")
            offering_total += self.offering_gems
        
        if offering_lines:
            embed.add_field(
                name=f"📦 Offering ({len(self.offering_items)} items)",
                value="\n".join(offering_lines[:10]) + (f"\n... +{len(offering_lines)-10} more" if len(offering_lines) > 10 else ""),
                inline=True
            )
        else:
            embed.add_field(name="📦 Offering", value="*No items added*", inline=True)
        
        requesting_lines = []
        requesting_total = 0
        for item in self.requesting_items:
            emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
            value = item.get('value', 0)
            requesting_total += value
            line = f"{emoji} **{item['name']}**"
            if value > 0:
                line += f" ({format_value(value)})"
            requesting_lines.append(line)
        
        if self.game == 'ps99' and self.requesting_gems > 0:
            requesting_lines.append(f"💎 **{format_value(self.requesting_gems)} Diamonds**")
            requesting_total += self.requesting_gems
        
        if requesting_lines:
            embed.add_field(
                name=f"🎯 Requesting ({len(self.requesting_items)} items)",
                value="\n".join(requesting_lines[:10]) + (f"\n... +{len(requesting_lines)-10} more" if len(requesting_lines) > 10 else ""),
                inline=True
            )
        else:
            embed.add_field(name="🎯 Requesting", value="*Open to offers*", inline=True)
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        value_diff = offering_total - requesting_total
        if offering_total > 0 or requesting_total > 0:
            value_text = f"**Offering:** {format_value(offering_total)}\n**Requesting:** {format_value(requesting_total)}\n"
            if value_diff > 0:
                value_text += f"📈 Overpaying by {format_value(abs(value_diff))}"
            elif value_diff < 0:
                value_text += f"📉 Underpaying by {format_value(abs(value_diff))}"
            else:
                value_text += "⚖️ Fair trade!"
            embed.add_field(name="💰 Value Analysis", value=value_text, inline=False)
        
        if self.notes:
            embed.add_field(name="📝 Notes", value=self.notes[:200], inline=False)
        
        embed.set_footer(text="Click 'Confirm Trade' when ready to post!")
        
        return embed
    
    def get_trade_data(self) -> Dict:
        return {
            'game': self.game,
            'offering_items': self.offering_items,
            'requesting_items': self.requesting_items,
            'offering_gems': self.offering_gems,
            'requesting_gems': self.requesting_gems,
            'notes': self.notes
        }


class AddOfferingItemButton(Button):
    def __init__(self):
        super().__init__(
            label="Add Offering Item",
            style=discord.ButtonStyle.success,
            emoji="➕",
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        modal = ItemSearchModal(self.view.game, "offering")
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.selected_item:
            self.view.offering_items.append(modal.selected_item)
            await interaction.edit_original_response(embed=self.view.get_summary_embed(), view=self.view)


class AddRequestingItemButton(Button):
    def __init__(self):
        super().__init__(
            label="Add Requesting Item",
            style=discord.ButtonStyle.primary,
            emoji="🎯",
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        modal = ItemSearchModal(self.view.game, "requesting")
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.selected_item:
            self.view.requesting_items.append(modal.selected_item)
            await interaction.edit_original_response(embed=self.view.get_summary_embed(), view=self.view)


class SetOfferingGemsButton(Button):
    def __init__(self):
        super().__init__(
            label="Add Offering 💎",
            style=discord.ButtonStyle.success,
            emoji="💎",
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        modal = GemInputModal("offering", self.view.offering_gems)
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.gem_amount is not None:
            self.view.offering_gems = modal.gem_amount
            await interaction.edit_original_response(embed=self.view.get_summary_embed(), view=self.view)


class SetRequestingGemsButton(Button):
    def __init__(self):
        super().__init__(
            label="Request 💎",
            style=discord.ButtonStyle.primary,
            emoji="💎",
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        modal = GemInputModal("requesting", self.view.requesting_gems)
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.gem_amount is not None:
            self.view.requesting_gems = modal.gem_amount
            await interaction.edit_original_response(embed=self.view.get_summary_embed(), view=self.view)


class AddNotesButton(Button):
    def __init__(self):
        super().__init__(
            label="Add Notes",
            style=discord.ButtonStyle.secondary,
            emoji="📝",
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        modal = NotesModal(self.view.notes)
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.notes_value is not None:
            self.view.notes = modal.notes_value
            await interaction.edit_original_response(embed=self.view.get_summary_embed(), view=self.view)


class PreviewTradeButton(Button):
    def __init__(self):
        super().__init__(
            label="Preview",
            style=discord.ButtonStyle.secondary,
            emoji="👁️",
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        embed = create_trade_preview_embed(
            self.view.get_trade_data(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfirmTradeButton(Button):
    def __init__(self):
        super().__init__(
            label="Confirm Trade",
            style=discord.ButtonStyle.success,
            emoji="✅",
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        if not self.view.offering_items and self.view.offering_gems == 0:
            await interaction.response.send_message(
                "You must offer at least one item or some gems!",
                ephemeral=True
            )
            return
        
        self.view.completed = True
        self.view.stop()
        await interaction.response.defer()


class CancelTradeButton(Button):
    def __init__(self):
        super().__init__(
            label="Cancel",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        self.view.cancelled = True
        self.view.stop()
        await interaction.response.send_message("Trade creation cancelled.", ephemeral=True)


class ItemSearchModal(Modal):
    def __init__(self, game: str, trade_side: str):
        super().__init__(title=f"Add Item to {trade_side.title()}")
        self.game = game
        self.trade_side = trade_side
        self.selected_item: Optional[Dict] = None
        
        self.item_name = TextInput(
            label="Item Name",
            placeholder="Enter item name (e.g., Huge Hacked Cat, Titanic Corgi)",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.add_item(self.item_name)
        
        self.quantity = TextInput(
            label="Quantity (optional)",
            placeholder="1",
            style=discord.TextStyle.short,
            required=False,
            max_length=10,
            default="1"
        )
        self.add_item(self.quantity)
    
    async def on_submit(self, interaction: discord.Interaction):
        from utils.resolver import item_resolver
        
        item_name = self.item_name.value.strip()
        
        try:
            qty = int(self.quantity.value) if self.quantity.value else 1
            qty = max(1, min(99, qty))
        except ValueError:
            qty = 1
        
        resolved = await item_resolver.resolve_item(self.game, item_name)
        
        if resolved:
            self.selected_item = {
                'id': resolved.get('id', item_name),
                'name': resolved.get('name', item_name),
                'rarity': resolved.get('rarity', 'Common'),
                'value': resolved.get('value', 0),
                'icon_url': resolved.get('icon_url', ''),
                'quantity': qty
            }
            await interaction.response.send_message(
                f"✅ Added **{resolved['name']}** x{qty} to your {self.trade_side}!",
                ephemeral=True
            )
        else:
            suggestions = await item_resolver.suggest_items(self.game, item_name, limit=5)
            if suggestions:
                suggestion_text = "\n".join([f"• {s['name']}" for s in suggestions])
                await interaction.response.send_message(
                    f"❌ Item '{item_name}' not found. Did you mean:\n{suggestion_text}",
                    ephemeral=True
                )
            else:
                self.selected_item = {
                    'id': item_name.lower().replace(' ', '_'),
                    'name': item_name,
                    'rarity': 'Unknown',
                    'value': 0,
                    'icon_url': '',
                    'quantity': qty
                }
                await interaction.response.send_message(
                    f"⚠️ Item '{item_name}' not in database. Added as custom item.",
                    ephemeral=True
                )


class GemInputModal(Modal):
    def __init__(self, trade_side: str, current_value: int = 0):
        super().__init__(title=f"Set {trade_side.title()} Diamonds")
        self.trade_side = trade_side
        self.gem_amount: Optional[int] = None
        
        self.gems = TextInput(
            label="Diamond Amount",
            placeholder="Enter amount (e.g., 500M, 1.5B, 2T)",
            style=discord.TextStyle.short,
            required=True,
            max_length=20,
            default=format_value(current_value) if current_value > 0 else ""
        )
        self.add_item(self.gems)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.gem_amount = parse_gem_value(self.gems.value)
        
        if self.gem_amount > 0:
            await interaction.response.send_message(
                f"💎 Set {self.trade_side} diamonds to **{format_value(self.gem_amount)}**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"💎 Cleared {self.trade_side} diamonds",
                ephemeral=True
            )


class NotesModal(Modal):
    def __init__(self, current_notes: str = ""):
        super().__init__(title="Trade Notes")
        self.notes_value: Optional[str] = None
        
        self.notes = TextInput(
            label="Notes",
            placeholder="Add any notes about this trade...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
            default=current_notes
        )
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.notes_value = self.notes.value.strip() if self.notes.value else ""
        await interaction.response.send_message("📝 Notes updated!", ephemeral=True)


class ItemSelectorView(View):
    def __init__(self, user_id: int, game: str, items: List[Dict], trade_side: str):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.game = game
        self.items = items
        self.trade_side = trade_side
        self.selected_items: List[Dict] = []
        self.current_page = 0
        self.items_per_page = 25
        
        self._build_selector()
    
    def _build_selector(self):
        self.clear_items()
        
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.items))
        page_items = self.items[start_idx:end_idx]
        
        if page_items:
            options = []
            for item in page_items:
                emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
                value = item.get('value', 0)
                description = f"{item.get('rarity', 'Common')} - {format_value(value)}" if value > 0 else item.get('rarity', 'Common')
                
                options.append(discord.SelectOption(
                    label=item['name'][:100],
                    value=item.get('id', item['name'])[:100],
                    description=description[:100],
                    emoji=emoji
                ))
            
            select = Select(
                placeholder=f"Select items to add ({start_idx+1}-{end_idx} of {len(self.items)})",
                options=options,
                min_values=0,
                max_values=len(options)
            )
            select.callback = self._on_select
            self.add_item(select)
        
        if len(self.items) > self.items_per_page:
            if self.current_page > 0:
                prev_btn = Button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=1)
                prev_btn.callback = self._prev_page
                self.add_item(prev_btn)
            
            if end_idx < len(self.items):
                next_btn = Button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
                next_btn.callback = self._next_page
                self.add_item(next_btn)
        
        confirm_btn = Button(label="Confirm Selection", style=discord.ButtonStyle.success, emoji="✅", row=2)
        confirm_btn.callback = self._confirm
        self.add_item(confirm_btn)
    
    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return
        
        select = interaction.data.get('values', [])
        self.selected_items = [item for item in self.items if item.get('id', item['name']) in select]
        await interaction.response.defer()
    
    async def _prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return
        self.current_page = max(0, self.current_page - 1)
        self._build_selector()
        await interaction.response.edit_message(view=self)
    
    async def _next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return
        max_page = (len(self.items) - 1) // self.items_per_page
        self.current_page = min(max_page, self.current_page + 1)
        self._build_selector()
        await interaction.response.edit_message(view=self)
    
    async def _confirm(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return
        self.stop()
        await interaction.response.defer()


def create_trade_preview_embed(trade_data: Dict, requester: discord.User) -> discord.Embed:
    from ui.embeds import GAME_NAMES, GAME_COLORS
    
    game = trade_data.get('game', 'unknown')
    color = GAME_COLORS.get(game, 0x7289DA)
    
    embed = discord.Embed(
        title=f"📋 Trade Preview - {GAME_NAMES.get(game, game.upper())}",
        color=color
    )
    embed.set_author(name=f"From: {requester.display_name}", icon_url=requester.display_avatar.url)
    
    offering_items = trade_data.get('offering_items', [])
    offering_gems = trade_data.get('offering_gems', 0)
    
    offering_lines = []
    total_offering = 0
    first_icon = None
    
    for item in offering_items:
        emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
        value = item.get('value', 0)
        qty = item.get('quantity', 1)
        total_offering += value * qty
        
        line = f"{emoji} **{item['name']}**"
        if qty > 1:
            line += f" x{qty}"
        if value > 0:
            line += f" ({format_value(value)})"
        offering_lines.append(line)
        
        if not first_icon and item.get('icon_url'):
            first_icon = item['icon_url']
    
    if offering_gems > 0:
        offering_lines.append(f"💎 **{format_value(offering_gems)} Diamonds**")
        total_offering += offering_gems
    
    if offering_lines:
        embed.add_field(
            name=f"📦 Offering",
            value="\n".join(offering_lines[:15]),
            inline=True
        )
    else:
        embed.add_field(name="📦 Offering", value="*Nothing*", inline=True)
    
    requesting_items = trade_data.get('requesting_items', [])
    requesting_gems = trade_data.get('requesting_gems', 0)
    
    requesting_lines = []
    total_requesting = 0
    
    for item in requesting_items:
        emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
        value = item.get('value', 0)
        qty = item.get('quantity', 1)
        total_requesting += value * qty
        
        line = f"{emoji} **{item['name']}**"
        if qty > 1:
            line += f" x{qty}"
        if value > 0:
            line += f" ({format_value(value)})"
        requesting_lines.append(line)
    
    if requesting_gems > 0:
        requesting_lines.append(f"💎 **{format_value(requesting_gems)} Diamonds**")
        total_requesting += requesting_gems
    
    if requesting_lines:
        embed.add_field(
            name=f"🎯 Requesting",
            value="\n".join(requesting_lines[:15]),
            inline=True
        )
    else:
        embed.add_field(name="🎯 Requesting", value="*Open to offers*", inline=True)
    
    if first_icon:
        embed.set_thumbnail(url=first_icon)
    
    value_diff = total_offering - total_requesting
    analysis = f"📦 {format_value(total_offering)} vs 🎯 {format_value(total_requesting)}\n"
    if value_diff > 0:
        analysis += f"📈 **+{format_value(abs(value_diff))}** overpay"
    elif value_diff < 0:
        analysis += f"📉 **-{format_value(abs(value_diff))}** underpay"
    else:
        analysis += "⚖️ **Fair trade!**"
    
    embed.add_field(name="💰 Value Analysis", value=analysis, inline=False)
    
    notes = trade_data.get('notes', '')
    if notes:
        embed.add_field(name="📝 Notes", value=notes[:200], inline=False)
    
    return embed


class QuickItemSelectView(View):
    def __init__(self, user_id: int, game: str, category: str = "all"):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.game = game
        self.category = category
        self.selected_items: List[Dict] = []
        
        categories = [
            discord.SelectOption(label="All Items", value="all", emoji="📦"),
            discord.SelectOption(label="Huge Pets", value="huge", emoji="💫"),
            discord.SelectOption(label="Titanic Pets", value="titanic", emoji="⭐"),
            discord.SelectOption(label="Mythic Pets", value="mythic", emoji="🔴"),
            discord.SelectOption(label="Legendary Pets", value="legendary", emoji="🟡"),
            discord.SelectOption(label="Exclusive/Event", value="exclusive", emoji="🎭"),
        ]
        
        cat_select = Select(
            placeholder="Filter by category...",
            options=categories,
            row=0
        )
        cat_select.callback = self._on_category_change
        self.add_item(cat_select)
    
    async def _on_category_change(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return
        self.category = interaction.data['values'][0]
        await interaction.response.defer()
