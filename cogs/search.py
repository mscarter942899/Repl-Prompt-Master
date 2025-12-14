import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List

from utils.resolver import item_resolver
from utils.database import get_all_items_for_game
from ui.embeds import SearchEmbed, GAME_NAMES, GAME_COLORS

class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._item_cache: dict = {}
    
    async def item_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        game = None
        if interaction.data:
            options = interaction.data.get('options', [])
            if options:
                for opt in options:
                    if isinstance(opt, dict) and opt.get('name') == 'game':
                        game = str(opt.get('value', ''))
                        break
        
        if not game:
            return []
        
        try:
            if not current or len(current) < 1:
                items = await get_all_items_for_game(game, limit=25)
                return [
                    app_commands.Choice(name=f"{item['name'][:50]} ({item.get('value', 0):,.0f})"[:100], value=item['name'][:100])
                    for item in items
                ]
            
            items = await item_resolver.search_items(game, current, limit=25)
            return [
                app_commands.Choice(name=f"{item['name'][:50]} ({item.get('value', 0):,.0f})"[:100], value=item['name'][:100])
                for item in items
            ]
        except Exception:
            return []
    
    @app_commands.command(name="search", description="Search for items in a game")
    @app_commands.describe(
        game="The game to search in",
        query="The item name to search for"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    @app_commands.autocomplete(query=item_autocomplete)
    async def search(self, interaction: discord.Interaction, game: str, query: str):
        await interaction.response.defer()
        
        items = await item_resolver.search_items(game, query, limit=10)
        
        embed = SearchEmbed.create_results(query, items, game)
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="item", description="Get details about a specific item")
    @app_commands.describe(
        game="The game this item is from",
        name="The item name"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    @app_commands.autocomplete(name=item_autocomplete)
    async def item_info(self, interaction: discord.Interaction, game: str, name: str):
        await interaction.response.defer()
        
        item = await item_resolver.resolve_item(game, name)
        
        if not item:
            suggestions = await item_resolver.suggest_items(game, name, limit=3)
            if suggestions:
                suggestion_text = ", ".join([s['name'] for s in suggestions])
                await interaction.followup.send(
                    f"Item not found. Did you mean: **{suggestion_text}**?",
                    ephemeral=True
                )
            else:
                await interaction.followup.send("Item not found.", ephemeral=True)
            return
        
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(
            title=item['name'],
            color=color
        )
        
        if item.get('icon_url'):
            embed.set_thumbnail(url=item['icon_url'])
        
        embed.add_field(name="Game", value=GAME_NAMES.get(game, game.upper()), inline=True)
        embed.add_field(name="Rarity", value=item.get('rarity', 'Unknown'), inline=True)
        
        value = item.get('value', 0)
        if value >= 1_000_000_000_000:
            value_str = f"{value/1_000_000_000_000:.2f}T"
        elif value >= 1_000_000_000:
            value_str = f"{value/1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            value_str = f"{value/1_000_000:.2f}M"
        elif value >= 1_000:
            value_str = f"{value/1_000:.2f}K"
        else:
            value_str = f"{value:,.0f}"
        embed.add_field(name="Value", value=value_str, inline=True)
        
        metadata = item.get('metadata', {})
        rap = metadata.get('rap', 0)
        if rap and game == 'ps99':
            if rap >= 1_000_000_000_000:
                rap_str = f"{rap/1_000_000_000_000:.2f}T"
            elif rap >= 1_000_000_000:
                rap_str = f"{rap/1_000_000_000:.2f}B"
            elif rap >= 1_000_000:
                rap_str = f"{rap/1_000_000:.2f}M"
            elif rap >= 1_000:
                rap_str = f"{rap/1_000:.2f}K"
            else:
                rap_str = f"{rap:,.0f}"
            embed.add_field(name="RAP", value=rap_str, inline=True)
        
        embed.add_field(name="Tradeable", value="Yes" if item.get('tradeable', True) else "No", inline=True)
        embed.add_field(name="Item ID", value=item.get('id', 'N/A'), inline=True)
        
        if metadata:
            meta_text = []
            for key, val in metadata.items():
                if key == 'rap':
                    continue
                if val and val != False:
                    if isinstance(val, bool):
                        meta_text.append(key.replace('_', ' ').title())
                    elif isinstance(val, (int, float)) and val > 0:
                        meta_text.append(f"{key.replace('_', ' ').title()}: {val:,.0f}")
                    elif isinstance(val, str):
                        meta_text.append(f"{key.replace('_', ' ').title()}: {val}")
            if meta_text:
                embed.add_field(name="Properties", value="\n".join(meta_text), inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="values", description="View current item values for a game")
    @app_commands.describe(game="The game to view values for")
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def values(self, interaction: discord.Interaction, game: str):
        await interaction.response.defer()
        
        items = await get_all_items_for_game(game, limit=15)
        
        if not items:
            await interaction.followup.send(
                f"No items found for this game.\nUse `/manage add` to add items.",
                ephemeral=True
            )
            return
        
        color = GAME_COLORS.get(game, 0x7289DA)
        embed = discord.Embed(
            title=f"Top Items - {GAME_NAMES.get(game, game.upper())}",
            description="Sorted by value (highest first)",
            color=color
        )
        
        for i, item in enumerate(items, 1):
            name = item.get('name', 'Unknown')
            value = item.get('value', 0)
            rarity = item.get('rarity', 'Unknown')
            
            embed.add_field(
                name=f"{i}. {name}",
                value=f"Value: {value:,.0f}\nRarity: {rarity}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SearchCog(bot))
