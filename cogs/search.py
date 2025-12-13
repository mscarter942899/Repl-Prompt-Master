import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.resolver import item_resolver
from api.base import APIRegistry
from ui.embeds import SearchEmbed, GAME_NAMES, GAME_COLORS

class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
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
        embed.add_field(name="Value", value=f"{item.get('value', 0):,.0f}", inline=True)
        embed.add_field(name="Tradeable", value="Yes" if item.get('tradeable', True) else "No", inline=True)
        embed.add_field(name="Item ID", value=item.get('id', 'N/A'), inline=True)
        
        metadata = item.get('metadata', {})
        if metadata:
            meta_text = []
            for key, value in metadata.items():
                if value and value != False:
                    if isinstance(value, bool):
                        meta_text.append(key.replace('_', ' ').title())
                    else:
                        meta_text.append(f"{key.replace('_', ' ').title()}: {value}")
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
        
        adapter = APIRegistry.get(game)
        if not adapter:
            await interaction.followup.send("Game not found.", ephemeral=True)
            return
        
        items = await adapter.fetch_items()
        
        if not items:
            await interaction.followup.send("No items found.", ephemeral=True)
            return
        
        sorted_items = sorted(items, key=lambda x: x.get('value', 0), reverse=True)[:15]
        
        color = GAME_COLORS.get(game, 0x7289DA)
        embed = discord.Embed(
            title=f"Top Items - {GAME_NAMES.get(game, game.upper())}",
            description="Sorted by value (highest first)",
            color=color
        )
        
        for i, item in enumerate(sorted_items, 1):
            name = item.get('name', 'Unknown')
            value = item.get('value', 0)
            rarity = item.get('rarity', 'Unknown')
            
            embed.add_field(
                name=f"{i}. {name}",
                value=f"Value: {value:,.0f}\nRarity: {rarity}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="api_status", description="Check game API status")
    async def api_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        status = await APIRegistry.health_check_all()
        
        embed = discord.Embed(
            title="API Status",
            color=0x2ECC71 if all(status.values()) else 0xE74C3C
        )
        
        for game, healthy in status.items():
            emoji = "✅" if healthy else "❌"
            name = GAME_NAMES.get(game, game.upper())
            embed.add_field(name=name, value=f"{emoji} {'Online' if healthy else 'Offline'}", inline=True)
        
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SearchCog(bot))
