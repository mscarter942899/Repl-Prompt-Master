import discord
from discord.ui import View, Button, Select, Modal, TextInput
from typing import Optional, List, Dict, Any, TYPE_CHECKING, cast, Union
import json

DIAMONDS_EMOJI = "<:diamonds:1449866490495893577>"

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

GAME_THEMES = {
    'ps99': {'color': 0x9B59B6, 'emoji': '🐾', 'name': 'Pet Simulator 99'},
    'gag': {'color': 0x2ECC71, 'emoji': '🌱', 'name': 'Grow a Garden'},
    'am': {'color': 0xE74C3C, 'emoji': '🏠', 'name': 'Adopt Me'},
    'bf': {'color': 0x3498DB, 'emoji': '🍎', 'name': 'Blox Fruits'},
    'sab': {'color': 0xF39C12, 'emoji': '🧠', 'name': 'Steal a Brainrot'}
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
        super().__init__(timeout=900)
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
        self.current_mode = "main"
        self.message: Optional[discord.Message] = None
        
        self._build_main_view()
    
    def _build_main_view(self):
        self.clear_items()
        self.current_mode = "main"
        
        self.add_item(BrowseItemsButton("offering"))
        self.add_item(BrowseItemsButton("requesting"))
        self.add_item(QuickAddButton("offering"))
        self.add_item(QuickAddButton("requesting"))
        
        if self.game == 'ps99':
            self.add_item(GemsButton("offering", self.offering_gems))
            self.add_item(GemsButton("requesting", self.requesting_gems))
        
        if self.offering_items:
            self.add_item(ManageItemsButton("offering", len(self.offering_items)))
        if self.requesting_items:
            self.add_item(ManageItemsButton("requesting", len(self.requesting_items)))
        
        self.add_item(NotesButton(bool(self.notes)))
        self.add_item(PreviewButton())
        self.add_item(ConfirmButton())
        self.add_item(CancelButton())
    
    def get_summary_embed(self) -> discord.Embed:
        theme = GAME_THEMES.get(self.game, {'color': 0x7289DA, 'emoji': '📦', 'name': self.game.upper()})
        
        embed = discord.Embed(
            title=f"{theme['emoji']} Trade Builder - {theme['name']}",
            description="Create your perfect trade offer using the buttons below!",
            color=theme['color']
        )
        
        offering_lines = []
        offering_total = 0
        first_icon = None
        
        for item in self.offering_items:
            emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
            value = item.get('value', 0)
            qty = item.get('quantity', 1)
            offering_total += value * qty
            
            line = f"{emoji} **{item['name']}**"
            if qty > 1:
                line += f" x{qty}"
            if value > 0:
                line += f" • {format_value(value)}"
            offering_lines.append(line)
            
            if not first_icon and item.get('icon_url'):
                first_icon = item['icon_url']
        
        if self.game == 'ps99' and self.offering_gems > 0:
            offering_lines.append(f"{DIAMONDS_EMOJI} **{format_value(self.offering_gems)} Diamonds**")
            offering_total += self.offering_gems
        
        offering_header = f"📦 YOUR OFFER"
        if self.offering_items:
            offering_header += f" ({len(self.offering_items)} items)"
        
        if offering_lines:
            offer_text = "\n".join(offering_lines[:8])
            if len(offering_lines) > 8:
                offer_text += f"\n*+{len(offering_lines)-8} more items...*"
            embed.add_field(name=offering_header, value=offer_text, inline=True)
        else:
            embed.add_field(name=offering_header, value="*Click 'Browse Items' or 'Quick Add' to add items*", inline=True)
        
        requesting_lines = []
        requesting_total = 0
        
        for item in self.requesting_items:
            emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
            value = item.get('value', 0)
            qty = item.get('quantity', 1)
            requesting_total += value * qty
            
            line = f"{emoji} **{item['name']}**"
            if qty > 1:
                line += f" x{qty}"
            if value > 0:
                line += f" • {format_value(value)}"
            requesting_lines.append(line)
        
        if self.game == 'ps99' and self.requesting_gems > 0:
            requesting_lines.append(f"{DIAMONDS_EMOJI} **{format_value(self.requesting_gems)} Diamonds**")
            requesting_total += self.requesting_gems
        
        requesting_header = f"🎯 YOU WANT"
        if self.requesting_items:
            requesting_header += f" ({len(self.requesting_items)} items)"
        
        if requesting_lines:
            request_text = "\n".join(requesting_lines[:8])
            if len(requesting_lines) > 8:
                request_text += f"\n*+{len(requesting_lines)-8} more items...*"
            embed.add_field(name=requesting_header, value=request_text, inline=True)
        else:
            embed.add_field(name=requesting_header, value="*Leave empty for open offers*", inline=True)
        
        if offering_total > 0 or requesting_total > 0:
            value_diff = offering_total - requesting_total
            
            analysis_lines = [
                f"📊 **Your Offer:** {format_value(offering_total)}",
                f"📊 **You Want:** {format_value(requesting_total)}"
            ]
            
            if requesting_total > 0:
                if value_diff > 0:
                    pct = (value_diff / requesting_total * 100) if requesting_total > 0 else 0
                    analysis_lines.append(f"\n📈 **OVERPAY** by {format_value(abs(value_diff))} (+{pct:.1f}%)")
                elif value_diff < 0:
                    pct = (abs(value_diff) / offering_total * 100) if offering_total > 0 else 0
                    analysis_lines.append(f"\n📉 **UNDERPAY** by {format_value(abs(value_diff))} (-{pct:.1f}%)")
                else:
                    analysis_lines.append("\n⚖️ **FAIR TRADE**")
            
            embed.add_field(name="💰 Value Analysis", value="\n".join(analysis_lines), inline=False)
        
        if self.notes:
            embed.add_field(name="📝 Notes", value=self.notes[:200], inline=False)
        
        status_parts = []
        if self.offering_items or self.offering_gems > 0:
            status_parts.append("✅ Offer ready")
        else:
            status_parts.append("⚠️ Add items to offer")
        
        embed.set_footer(text=" • ".join(status_parts) + " | Click ✅ Confirm when ready!")
        
        if first_icon:
            embed.set_thumbnail(url=first_icon)
        
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


class BrowseItemsButton(Button):
    view: "TradeBuilderView"
    
    def __init__(self, side: str):
        self.side = side
        emoji = "📦" if side == "offering" else "🎯"
        label = "Browse Items (Offer)" if side == "offering" else "Browse Items (Want)"
        style = discord.ButtonStyle.success if side == "offering" else discord.ButtonStyle.primary
        super().__init__(label=label, emoji=emoji, style=style, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        from utils.database import get_all_items_for_game
        
        items = await get_all_items_for_game(self.view.game, limit=100)
        
        if not items:
            await interaction.response.send_message(
                "No items found in database for this game. Use Quick Add instead!",
                ephemeral=True
            )
            return
        
        selector_view = ItemBrowserView(
            user_id=self.view.user_id,
            game=self.view.game,
            items=items,
            side=self.side,
            parent_view=self.view,
            parent_interaction=interaction
        )
        
        embed = selector_view.get_embed()
        await interaction.response.send_message(embed=embed, view=selector_view, ephemeral=True)


class QuickAddButton(Button):
    view: "TradeBuilderView"
    
    def __init__(self, side: str):
        self.side = side
        emoji = "➕" if side == "offering" else "🔍"
        label = "Quick Add (Offer)" if side == "offering" else "Quick Add (Want)"
        style = discord.ButtonStyle.secondary
        super().__init__(label=label, emoji=emoji, style=style, row=1)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        modal = QuickAddModal(self.view.game, self.side, self.view)
        await interaction.response.send_modal(modal)


class GemsButton(Button):
    view: "TradeBuilderView"
    
    def __init__(self, side: str, current_amount: int):
        self.side = side
        label = "Offer Gems" if side == "offering" else "Request Gems"
        if current_amount > 0:
            label = f"{format_value(current_amount)} Diamonds"
        style = discord.ButtonStyle.success if side == "offering" else discord.ButtonStyle.primary
        super().__init__(label=label, style=style, row=2)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        current = self.view.offering_gems if self.side == "offering" else self.view.requesting_gems
        modal = GemInputModal(self.side, current, self.view)
        await interaction.response.send_modal(modal)


class ManageItemsButton(Button):
    view: "TradeBuilderView"
    
    def __init__(self, side: str, count: int):
        self.side = side
        label = f"Manage Offer ({count})" if side == "offering" else f"Manage Wants ({count})"
        super().__init__(label=label, emoji="📋", style=discord.ButtonStyle.secondary, row=2)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        items = self.view.offering_items if self.side == "offering" else self.view.requesting_items
        
        if not items:
            await interaction.response.send_message("No items to manage!", ephemeral=True)
            return
        
        manage_view = ManageItemsView(
            user_id=self.view.user_id,
            items=items,
            side=self.side,
            parent_view=self.view,
            parent_interaction=interaction
        )
        
        embed = manage_view.get_embed()
        await interaction.response.send_message(embed=embed, view=manage_view, ephemeral=True)


class NotesButton(Button):
    view: "TradeBuilderView"
    
    def __init__(self, has_notes: bool):
        label = "📝 Notes" if not has_notes else "📝 Edit Notes"
        super().__init__(label=label, emoji="📝", style=discord.ButtonStyle.secondary, row=3)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        modal = NotesModal(self.view.notes, self.view)
        await interaction.response.send_modal(modal)


class PreviewButton(Button):
    view: "TradeBuilderView"
    
    def __init__(self):
        super().__init__(label="Preview", emoji="👁️", style=discord.ButtonStyle.secondary, row=3)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        embed = create_trade_preview_embed(self.view.get_trade_data(), interaction.user)
        await interaction.response.send_message(
            "**This is how your trade will appear to others:**",
            embed=embed,
            ephemeral=True
        )


class ConfirmButton(Button):
    view: "TradeBuilderView"
    
    def __init__(self):
        super().__init__(label="Confirm Trade", emoji="✅", style=discord.ButtonStyle.success, row=4)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        if not self.view.offering_items and self.view.offering_gems == 0:
            await interaction.response.send_message(
                "⚠️ You must offer at least one item or some diamonds!",
                ephemeral=True
            )
            return
        
        self.view.completed = True
        self.view.stop()
        await interaction.response.defer()


class CancelButton(Button):
    view: "TradeBuilderView"
    
    def __init__(self):
        super().__init__(label="Cancel", emoji="❌", style=discord.ButtonStyle.danger, row=4)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This isn't your trade builder!", ephemeral=True)
            return
        
        self.view.cancelled = True
        self.view.stop()
        await interaction.response.send_message("Trade creation cancelled.", ephemeral=True)


class ItemBrowserView(View):
    def __init__(self, user_id: int, game: str, items: List[Dict], side: str, parent_view: TradeBuilderView, parent_interaction: Optional[discord.Interaction] = None):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.game = game
        self.items = items
        self.side = side
        self.parent_view = parent_view
        self._parent_interaction = parent_interaction
        self.current_page = 0
        self.items_per_page = 25
        self.selected_items: List[Dict] = []
        self.filter_rarity = "all"
        self.search_query = ""
        
        self._build_view()
    
    def _get_filtered_items(self) -> List[Dict]:
        filtered = self.items
        
        if self.filter_rarity != "all":
            filtered = [i for i in filtered if i.get('rarity', '').lower() == self.filter_rarity.lower()]
        
        if self.search_query:
            query = self.search_query.lower()
            filtered = [i for i in filtered if query in i.get('name', '').lower()]
        
        return filtered
    
    def _build_view(self):
        self.clear_items()
        
        filtered_items = self._get_filtered_items()
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(filtered_items))
        page_items = filtered_items[start_idx:end_idx]
        
        if page_items:
            options = []
            for item in page_items:
                emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
                value = item.get('value', 0)
                desc = f"{item.get('rarity', 'Unknown')} • {format_value(value)}" if value > 0 else item.get('rarity', 'Unknown')
                
                item_id = str(item.get('item_id', item.get('id', item['name'])))[:100]
                options.append(discord.SelectOption(
                    label=item['name'][:100],
                    value=item_id,
                    description=desc[:100],
                    emoji=emoji
                ))
            
            select = Select(
                placeholder=f"Select items ({start_idx+1}-{end_idx} of {len(filtered_items)})",
                options=options,
                min_values=0,
                max_values=min(len(options), 10),
                row=0
            )
            select.callback = self._on_select
            self.add_item(select)
        
        rarity_options = [
            discord.SelectOption(label="All Rarities", value="all", emoji="🌈"),
            discord.SelectOption(label="Common", value="common", emoji="⚪"),
            discord.SelectOption(label="Uncommon", value="uncommon", emoji="🟢"),
            discord.SelectOption(label="Rare", value="rare", emoji="🔵"),
            discord.SelectOption(label="Epic", value="epic", emoji="🟣"),
            discord.SelectOption(label="Legendary", value="legendary", emoji="🟡"),
            discord.SelectOption(label="Mythic", value="mythic", emoji="🔴"),
            discord.SelectOption(label="Titanic", value="titanic", emoji="⭐"),
            discord.SelectOption(label="Huge", value="huge", emoji="💫"),
        ]
        
        filter_select = Select(
            placeholder="Filter by rarity...",
            options=rarity_options,
            row=1
        )
        filter_select.callback = self._on_filter
        self.add_item(filter_select)
        
        search_btn = Button(label="🔍 Search", style=discord.ButtonStyle.secondary, row=2)
        search_btn.callback = self._on_search
        self.add_item(search_btn)
        
        if len(filtered_items) > self.items_per_page:
            if self.current_page > 0:
                prev_btn = Button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=2)
                prev_btn.callback = self._prev_page
                self.add_item(prev_btn)
            
            max_page = (len(filtered_items) - 1) // self.items_per_page
            if self.current_page < max_page:
                next_btn = Button(label="Next ▶", style=discord.ButtonStyle.secondary, row=2)
                next_btn.callback = self._next_page
                self.add_item(next_btn)
        
        add_btn = Button(
            label=f"Add Selected ({len(self.selected_items)})",
            style=discord.ButtonStyle.success,
            emoji="✅",
            row=3,
            disabled=len(self.selected_items) == 0
        )
        add_btn.callback = self._add_selected
        self.add_item(add_btn)
        
        close_btn = Button(label="Close", style=discord.ButtonStyle.danger, emoji="❌", row=3)
        close_btn.callback = self._close
        self.add_item(close_btn)
    
    def get_embed(self) -> discord.Embed:
        theme = GAME_THEMES.get(self.game, {'color': 0x7289DA, 'emoji': '📦', 'name': self.game.upper()})
        side_text = "to offer" if self.side == "offering" else "that you want"
        
        embed = discord.Embed(
            title=f"{theme['emoji']} Browse {theme['name']} Items",
            description=f"Select items {side_text}. You can select up to 10 items at once.",
            color=theme['color']
        )
        
        filtered_items = self._get_filtered_items()
        
        if self.filter_rarity != "all":
            embed.add_field(name="🏷️ Filter", value=self.filter_rarity.title(), inline=True)
        
        if self.search_query:
            embed.add_field(name="🔍 Search", value=self.search_query, inline=True)
        
        embed.add_field(name="📊 Items", value=f"{len(filtered_items)} available", inline=True)
        
        if self.selected_items:
            selected_text = "\n".join([
                f"{RARITY_EMOJIS.get(i.get('rarity', 'Common'), '⚪')} {i['name']}"
                for i in self.selected_items[:5]
            ])
            if len(self.selected_items) > 5:
                selected_text += f"\n*+{len(self.selected_items)-5} more...*"
            embed.add_field(name=f"✅ Selected ({len(self.selected_items)})", value=selected_text, inline=False)
        
        if filtered_items and filtered_items[0].get('icon_url'):
            embed.set_thumbnail(url=filtered_items[0]['icon_url'])
        
        return embed
    
    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        selected_ids = interaction.data.get('values', []) if interaction.data else []
        filtered = self._get_filtered_items()
        
        self.selected_items = [
            item for item in filtered
            if str(item.get('item_id', item.get('id', item['name']))) in selected_ids
        ]
        
        self._build_view()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    async def _on_filter(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        values = interaction.data.get('values', ['all']) if interaction.data else ['all']
        self.filter_rarity = values[0] if values else 'all'
        self.current_page = 0
        self.selected_items = []
        self._build_view()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    async def _on_search(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        modal = SearchModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.query is not None:
            self.search_query = modal.query
            self.current_page = 0
            self.selected_items = []
            self._build_view()
            await interaction.edit_original_response(embed=self.get_embed(), view=self)
    
    async def _prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        self.current_page = max(0, self.current_page - 1)
        self._build_view()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    async def _next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        filtered = self._get_filtered_items()
        max_page = (len(filtered) - 1) // self.items_per_page
        self.current_page = min(max_page, self.current_page + 1)
        self._build_view()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    async def _add_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        if not self.selected_items:
            await interaction.response.send_message("No items selected!", ephemeral=True)
            return
        
        added_count = len(self.selected_items)
        for item in self.selected_items:
            item_data = {
                'id': str(item.get('item_id', item.get('id', item['name']))),
                'name': item['name'],
                'rarity': item.get('rarity', 'Common'),
                'value': item.get('value', 0),
                'icon_url': item.get('icon_url', ''),
                'quantity': 1
            }
            
            if self.side == "offering":
                self.parent_view.offering_items.append(item_data)
            else:
                self.parent_view.requesting_items.append(item_data)
        
        self.parent_view._build_main_view()
        
        await interaction.response.send_message(
            f"✅ Added {added_count} item(s) to your {self.side}!",
            ephemeral=True
        )
        
        try:
            if self.parent_view.message:
                await self.parent_view.message.edit(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
            else:
                if hasattr(self, '_parent_interaction') and self._parent_interaction:
                    await self._parent_interaction.edit_original_response(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
        except Exception:
            pass
        
        self.stop()
    
    async def _close(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        await interaction.response.defer()
        self.stop()


class ManageItemsView(View):
    def __init__(self, user_id: int, items: List[Dict], side: str, parent_view: TradeBuilderView, parent_interaction: Optional[discord.Interaction] = None):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.items = items
        self.side = side
        self.parent_view = parent_view
        self._parent_interaction = parent_interaction
        
        self._build_view()
    
    def _build_view(self):
        self.clear_items()
        
        if self.items:
            options = []
            for i, item in enumerate(self.items[:25]):
                emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
                value = item.get('value', 0)
                qty = item.get('quantity', 1)
                desc = f"Qty: {qty}"
                if value > 0:
                    desc += f" • Value: {format_value(value * qty)}"
                
                options.append(discord.SelectOption(
                    label=item['name'][:100],
                    value=str(i),
                    description=desc[:100],
                    emoji=emoji
                ))
            
            select = Select(
                placeholder="Select items to remove...",
                options=options,
                min_values=0,
                max_values=len(options),
                row=0
            )
            select.callback = self._on_select
            self.add_item(select)
        
        clear_btn = Button(label="Clear All", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
        clear_btn.callback = self._clear_all
        self.add_item(clear_btn)
        
        close_btn = Button(label="Done", style=discord.ButtonStyle.success, emoji="✅", row=1)
        close_btn.callback = self._close
        self.add_item(close_btn)
    
    def get_embed(self) -> discord.Embed:
        side_text = "Offering" if self.side == "offering" else "Requesting"
        
        embed = discord.Embed(
            title=f"📋 Manage {side_text} Items",
            description="Select items to remove from your trade.",
            color=0x3498DB
        )
        
        items_text = []
        total_value = 0
        
        for i, item in enumerate(self.items[:15], 1):
            emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
            value = item.get('value', 0)
            qty = item.get('quantity', 1)
            total_value += value * qty
            
            line = f"{i}. {emoji} **{item['name']}**"
            if qty > 1:
                line += f" x{qty}"
            if value > 0:
                line += f" • {format_value(value * qty)}"
            items_text.append(line)
        
        if len(self.items) > 15:
            items_text.append(f"*...and {len(self.items) - 15} more items*")
        
        embed.add_field(name="Items", value="\n".join(items_text) or "No items", inline=False)
        embed.add_field(name="Total Value", value=format_value(total_value), inline=True)
        embed.add_field(name="Item Count", value=str(len(self.items)), inline=True)
        
        return embed
    
    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        values = interaction.data.get('values', []) if interaction.data else []
        indices = [int(v) for v in values]
        indices.sort(reverse=True)
        
        removed_names = []
        for idx in indices:
            if 0 <= idx < len(self.items):
                removed_names.append(self.items[idx]['name'])
                self.items.pop(idx)
        
        if self.side == "offering":
            self.parent_view.offering_items = self.items
        else:
            self.parent_view.requesting_items = self.items
        
        self.parent_view._build_main_view()
        
        if removed_names:
            await interaction.response.send_message(
                f"🗑️ Removed: {', '.join(removed_names[:5])}" + (f" +{len(removed_names)-5} more" if len(removed_names) > 5 else ""),
                ephemeral=True
            )
        else:
            await interaction.response.defer()
        
        try:
            if self.parent_view.message:
                await self.parent_view.message.edit(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
            elif self._parent_interaction:
                await self._parent_interaction.edit_original_response(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
        except Exception:
            pass
        
        if self.items:
            self._build_view()
        else:
            self.stop()
    
    async def _clear_all(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        count = len(self.items)
        self.items.clear()
        
        if self.side == "offering":
            self.parent_view.offering_items = []
        else:
            self.parent_view.requesting_items = []
        
        self.parent_view._build_main_view()
        
        await interaction.response.send_message(f"🗑️ Cleared {count} items!", ephemeral=True)
        
        try:
            if self.parent_view.message:
                await self.parent_view.message.edit(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
            elif self._parent_interaction:
                await self._parent_interaction.edit_original_response(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
        except Exception:
            pass
        
        self.stop()
    
    async def _close(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        
        await interaction.response.defer()
        self.stop()


class QuickAddModal(Modal):
    def __init__(self, game: str, side: str, parent_view: Optional["TradeBuilderView"] = None):
        super().__init__(title=f"Quick Add Item")
        self.game = game
        self.side = side
        self.selected_item: Optional[Dict] = None
        self.parent_view = parent_view
        
        self.item_name = TextInput(
            label="Item Name",
            placeholder="e.g., Huge Hacked Cat, Titanic Corgi, Rainbow Dragon",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.add_item(self.item_name)
        
        self.quantity = TextInput(
            label="Quantity",
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
                'id': resolved.get('item_id', resolved.get('id', item_name)),
                'name': resolved.get('name', item_name),
                'rarity': resolved.get('rarity', 'Common'),
                'value': resolved.get('value', 0),
                'icon_url': resolved.get('icon_url', ''),
                'quantity': qty
            }
            
            if self.parent_view:
                if self.side == "offering":
                    self.parent_view.offering_items.append(self.selected_item)
                else:
                    self.parent_view.requesting_items.append(self.selected_item)
                
                self.parent_view._build_main_view()
                
                try:
                    if self.parent_view.message:
                        await self.parent_view.message.edit(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
                except Exception:
                    pass
            
            emoji = RARITY_EMOJIS.get(resolved.get('rarity', 'Common'), '⚪')
            value = resolved.get('value', 0)
            value_text = f" • Value: {format_value(value)}" if value > 0 else ""
            
            await interaction.response.send_message(
                f"✅ Added {emoji} **{resolved['name']}** x{qty}{value_text}",
                ephemeral=True
            )
        else:
            suggestions = await item_resolver.suggest_items(self.game, item_name, limit=5)
            if suggestions:
                suggestion_text = "\n".join([
                    f"{RARITY_EMOJIS.get(s.get('rarity', 'Common'), '⚪')} {s['name']}"
                    for s in suggestions
                ])
                await interaction.response.send_message(
                    f"❌ **'{item_name}'** not found. Did you mean:\n{suggestion_text}\n\n*Try again with the exact name!*",
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
                
                if self.parent_view:
                    if self.side == "offering":
                        self.parent_view.offering_items.append(self.selected_item)
                    else:
                        self.parent_view.requesting_items.append(self.selected_item)
                    
                    self.parent_view._build_main_view()
                    
                    try:
                        if self.parent_view.message:
                            await self.parent_view.message.edit(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
                    except Exception:
                        pass
                
                await interaction.response.send_message(
                    f"⚠️ **'{item_name}'** not in database. Added as custom item.",
                    ephemeral=True
                )


class GemInputModal(Modal):
    def __init__(self, side: str, current_value: int = 0, parent_view: Optional["TradeBuilderView"] = None):
        side_text = "Offer" if side == "offering" else "Request"
        super().__init__(title=f"{side_text} Diamonds")
        self.side = side
        self.gem_amount: Optional[int] = None
        self.parent_view = parent_view
        
        self.gems = TextInput(
            label="Diamond Amount",
            placeholder="Enter amount: 500M, 1.5B, 2T, etc.",
            style=discord.TextStyle.short,
            required=True,
            max_length=20,
            default=format_value(current_value) if current_value > 0 else ""
        )
        self.add_item(self.gems)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.gem_amount = parse_gem_value(self.gems.value)
        
        if self.parent_view:
            if self.side == "offering":
                self.parent_view.offering_gems = self.gem_amount
            else:
                self.parent_view.requesting_gems = self.gem_amount
            
            self.parent_view._build_main_view()
            
            try:
                if self.parent_view.message:
                    await self.parent_view.message.edit(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
            except Exception:
                pass
        
        if self.gem_amount > 0:
            side_text = "offering" if self.side == "offering" else "requesting"
            await interaction.response.send_message(
                f"{DIAMONDS_EMOJI} Now {side_text} **{format_value(self.gem_amount)} Diamonds**!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"{DIAMONDS_EMOJI} Cleared diamonds from trade.",
                ephemeral=True
            )


class NotesModal(Modal):
    def __init__(self, current_notes: str = "", parent_view: Optional["TradeBuilderView"] = None):
        super().__init__(title="Trade Notes")
        self.notes_value: Optional[str] = None
        self.parent_view = parent_view
        
        self.notes = TextInput(
            label="Notes (visible to trade partner)",
            placeholder="Add any details about your trade...\ne.g., 'Willing to add if needed' or 'Firm on this offer'",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
            default=current_notes
        )
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.notes_value = self.notes.value.strip() if self.notes.value else ""
        
        if self.parent_view:
            self.parent_view.notes = self.notes_value
            self.parent_view._build_main_view()
            
            try:
                if self.parent_view.message:
                    await self.parent_view.message.edit(embed=self.parent_view.get_summary_embed(), view=self.parent_view)
            except Exception:
                pass
        
        if self.notes_value:
            await interaction.response.send_message("Notes saved!", ephemeral=True)
        else:
            await interaction.response.send_message("Notes cleared!", ephemeral=True)


class SearchModal(Modal):
    def __init__(self):
        super().__init__(title="🔍 Search Items")
        self.query: Optional[str] = None
        
        self.search = TextInput(
            label="Search Query",
            placeholder="Enter item name to search...",
            style=discord.TextStyle.short,
            required=False,
            max_length=100
        )
        self.add_item(self.search)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.query = self.search.value.strip() if self.search.value else ""
        await interaction.response.defer()


def create_trade_preview_embed(trade_data: Dict, requester: "Union[discord.User, discord.Member]") -> discord.Embed:
    game = trade_data.get('game', 'unknown')
    theme = GAME_THEMES.get(game, {'color': 0x7289DA, 'emoji': '📦', 'name': game.upper()})
    
    embed = discord.Embed(
        title=f"{theme['emoji']} Trade Offer",
        color=theme['color']
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
        offering_lines.append(f"{DIAMONDS_EMOJI} **{format_value(offering_gems)} Diamonds**")
        total_offering += offering_gems
    
    if offering_lines:
        offer_text = "\n".join(offering_lines[:10])
        if len(offering_lines) > 10:
            offer_text += f"\n*+{len(offering_lines)-10} more...*"
        embed.add_field(name="📦 Offering", value=offer_text, inline=True)
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
        requesting_lines.append(f"{DIAMONDS_EMOJI} **{format_value(requesting_gems)} Diamonds**")
        total_requesting += requesting_gems
    
    if requesting_lines:
        request_text = "\n".join(requesting_lines[:10])
        if len(requesting_lines) > 10:
            request_text += f"\n*+{len(requesting_lines)-10} more...*"
        embed.add_field(name="🎯 Requesting", value=request_text, inline=True)
    else:
        embed.add_field(name="🎯 Requesting", value="*Open to offers*", inline=True)
    
    if total_offering > 0 or total_requesting > 0:
        value_diff = total_offering - total_requesting
        analysis = f"Offer: {format_value(total_offering)}\n"
        if total_requesting > 0:
            analysis += f"Want: {format_value(total_requesting)}\n"
            if value_diff > 0:
                analysis += f"📈 Overpay: {format_value(abs(value_diff))}"
            elif value_diff < 0:
                analysis += f"📉 Underpay: {format_value(abs(value_diff))}"
            else:
                analysis += "⚖️ Fair trade"
        embed.add_field(name="💰 Value", value=analysis, inline=True)
    
    notes = trade_data.get('notes', '')
    if notes:
        embed.add_field(name="📝 Notes", value=notes[:200], inline=False)
    
    embed.add_field(name="🎮 Game", value=theme['name'], inline=True)
    
    if first_icon:
        embed.set_thumbnail(url=first_icon)
    
    embed.set_footer(text="Click buttons below to respond!")
    
    return embed


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
                
                item_id = str(item.get('item_id', item.get('id', item['name'])))[:100]
                options.append(discord.SelectOption(
                    label=item['name'][:100],
                    value=item_id,
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
        
        selected_ids = interaction.data.get('values', []) if interaction.data else []
        self.selected_items = [
            item for item in self.items 
            if str(item.get('item_id', item.get('id', item['name']))) in selected_ids
        ]
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
