import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.database import (
    get_user, create_user, get_inventory, 
    add_to_inventory, remove_from_inventory
)
from utils.resolver import item_resolver
from ui.embeds import InventoryEmbed
from ui.views import PaginatorView, GameSelectView
from ui.modals import InventoryAddModal

class InventoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    inventory_group = app_commands.Group(name="inventory", description="Inventory management commands")
    
    @inventory_group.command(name="view", description="View your inventory")
    @app_commands.describe(
        game="Filter by game",
        user="View another user's inventory"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="All Games", value="all"),
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def inventory_view(self, interaction: discord.Interaction, game: str = "all", user: Optional[discord.User] = None):
        target_user = user or interaction.user
        
        game_filter = None if game == "all" else game
        items = await get_inventory(target_user.id, game_filter)
        
        if not items:
            await interaction.response.send_message(
                f"{'Your' if target_user == interaction.user else f'{target_user.display_name}\\'s'} inventory is empty.",
                ephemeral=True
            )
            return
        
        if game_filter:
            embed = InventoryEmbed.create(target_user, items, game_filter)
            await interaction.response.send_message(embed=embed)
        else:
            games = {}
            for item in items:
                g = item.get('game', 'unknown')
                if g not in games:
                    games[g] = []
                games[g].append(item)
            
            pages = []
            for g, g_items in games.items():
                pages.append(InventoryEmbed.create(target_user, g_items, g))
            
            if len(pages) == 1:
                await interaction.response.send_message(embed=pages[0])
            else:
                view = PaginatorView(pages, interaction.user.id)
                await interaction.response.send_message(embed=pages[0], view=view)
    
    @inventory_group.command(name="add", description="Add an item to your inventory")
    @app_commands.describe(game="The game this item is from")
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def inventory_add(self, interaction: discord.Interaction, game: str):
        user = await get_user(interaction.user.id)
        if not user:
            await create_user(interaction.user.id, str(interaction.user.created_at))
        
        modal = InventoryAddModal(game)
        await interaction.response.send_modal(modal)
        
        await modal.wait()
        
        if not modal.item_data:
            return
        
        item = await item_resolver.resolve_item(game, modal.item_data['name'])
        
        if not item:
            suggestions = await item_resolver.suggest_items(game, modal.item_data['name'], limit=3)
            if suggestions:
                suggestion_text = ", ".join([s['name'] for s in suggestions])
                await interaction.followup.send(
                    f"Item not found. Did you mean: {suggestion_text}?",
                    ephemeral=True
                )
            else:
                await interaction.followup.send("Item not found in the database.", ephemeral=True)
            return
        
        await add_to_inventory(
            interaction.user.id,
            game,
            item['id'],
            modal.item_data['quantity']
        )
        
        embed = discord.Embed(
            title="Item Added",
            description=f"Added **{modal.item_data['quantity']}x {item['name']}** to your inventory.",
            color=0x2ECC71
        )
        
        if item.get('icon_url'):
            embed.set_thumbnail(url=item['icon_url'])
        
        embed.add_field(name="Game", value=game.upper(), inline=True)
        embed.add_field(name="Rarity", value=item.get('rarity', 'Unknown'), inline=True)
        embed.add_field(name="Value", value=f"{item.get('value', 0):,.0f}", inline=True)
        
        await interaction.followup.send(embed=embed)
    
    @inventory_group.command(name="remove", description="Remove an item from your inventory")
    @app_commands.describe(
        game="The game this item is from",
        item_name="The item to remove",
        quantity="How many to remove"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def inventory_remove(self, interaction: discord.Interaction, game: str, item_name: str, quantity: int = 1):
        item = await item_resolver.resolve_item(game, item_name)
        
        if not item:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return
        
        success = await remove_from_inventory(
            interaction.user.id,
            game,
            item['id'],
            quantity
        )
        
        if success:
            await interaction.response.send_message(
                f"Removed **{quantity}x {item['name']}** from your inventory.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "You don't have enough of this item to remove.",
                ephemeral=True
            )
    
    @inventory_group.command(name="trade_list", description="View items you have marked for trade")
    @app_commands.describe(game="Filter by game")
    @app_commands.choices(game=[
        app_commands.Choice(name="All Games", value="all"),
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def inventory_trade_list(self, interaction: discord.Interaction, game: str = "all"):
        game_filter = None if game == "all" else game
        items = await get_inventory(interaction.user.id, game_filter)
        
        trade_items = [i for i in items if i.get('for_trade')]
        
        if not trade_items:
            await interaction.response.send_message("You have no items marked for trade.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Your Items For Trade",
            color=0x3498DB
        )
        
        for item in trade_items[:15]:
            name = item.get('name', 'Unknown')
            qty = item.get('quantity', 1)
            game_name = item.get('game', '').upper()
            value = item.get('value', 0)
            
            embed.add_field(
                name=f"{name} x{qty}",
                value=f"Game: {game_name}\nValue: {value:,.0f}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(InventoryCog(bot))
