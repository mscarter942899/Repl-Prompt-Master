import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json
import os

from api.base import APIRegistry
from utils.database import init_database, bulk_upsert_items, get_item_count


def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.client.application:
            if interaction.client.application.owner:
                return interaction.user.id == interaction.client.application.owner.id
            if interaction.client.application.team:
                return interaction.user.id in [m.id for m in interaction.client.application.team.members]
        return False
    return app_commands.check(predicate)


class OwnerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    owner_group = app_commands.Group(name="owner", description="Bot owner commands")
    
    @owner_group.command(name="sync", description="Sync slash commands")
    @is_owner()
    async def sync_commands(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"Synced {len(synced)} commands globally.")
        except Exception as e:
            await interaction.followup.send(f"Failed to sync: {e}")
    
    @owner_group.command(name="sync_guild", description="Sync commands to current guild")
    @is_owner()
    async def sync_guild(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            if interaction.guild:
                self.bot.tree.copy_global_to(guild=interaction.guild)
                synced = await self.bot.tree.sync(guild=interaction.guild)
                await interaction.followup.send(f"Synced {len(synced)} commands to this guild.")
            else:
                await interaction.followup.send("This command must be used in a guild.")
        except Exception as e:
            await interaction.followup.send(f"Failed to sync: {e}")
    
    @owner_group.command(name="reload", description="Reload a cog")
    @is_owner()
    @app_commands.describe(cog="The cog to reload")
    async def reload_cog(self, interaction: discord.Interaction, cog: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await interaction.response.send_message(f"Reloaded {cog}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to reload: {e}", ephemeral=True)
    
    @owner_group.command(name="status", description="View bot status")
    @is_owner()
    async def bot_status(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Bot Status",
            color=0x2ECC71
        )
        
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        embed.add_field(name="Users", value=str(total_members), inline=True)
        embed.add_field(name="Latency", value=f"{self.bot.latency*1000:.0f}ms", inline=True)
        
        total_items = await get_item_count()
        embed.add_field(name="Items in DB", value=str(total_items), inline=True)
        
        cogs_loaded = list(self.bot.cogs.keys())
        embed.add_field(name="Cogs Loaded", value=", ".join(cogs_loaded) or "None", inline=False)
        
        api_status = await APIRegistry.health_check_all()
        api_text = "\n".join([f"{'✅' if v else '❌'} {k.upper()}" for k, v in api_status.items()])
        embed.add_field(name="API Status", value=api_text or "No APIs", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @owner_group.command(name="refresh_cache", description="Refresh all item caches and save to database")
    @is_owner()
    async def refresh_cache(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        refreshed = []
        for game, adapter in APIRegistry.all().items():
            try:
                adapter._cache.clear()
                adapter._cache_expiry.clear()
                items = await adapter.fetch_items()
                if items:
                    count = await bulk_upsert_items(items, source='api')
                    refreshed.append(f"✅ {game.upper()}: {count} items saved to database")
                else:
                    refreshed.append(f"⚠️ {game.upper()}: No items fetched")
            except Exception as e:
                refreshed.append(f"❌ {game.upper()}: {str(e)[:50]}")
        
        await interaction.followup.send("\n".join(refreshed))
    
    @owner_group.command(name="set_source", description="Set custom scraping URL for a game")
    @is_owner()
    @app_commands.describe(
        game="The game to change the source for",
        url="The new URL to scrape values from"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def set_source(self, interaction: discord.Interaction, game: str, url: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            from utils.database import set_game_source, init_database
            
            await init_database()
            
            await set_game_source(game, url, interaction.user.id)
            
            adapter = APIRegistry.get(game)
            if adapter:
                adapter._cache.clear()
                adapter._cache_expiry.clear()
                adapter.values_url = url
                
                items = await adapter.fetch_items()
                item_count = len(items) if items else 0
                
                await interaction.followup.send(
                    f"✅ Updated source URL for **{game.upper()}**\n"
                    f"New URL: {url}\n"
                    f"Fetched: {item_count} items"
                )
            else:
                await interaction.followup.send(f"❌ Game '{game}' not found")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")
    
    @owner_group.command(name="view_sources", description="View current scraping URLs for all games")
    @is_owner()
    async def view_sources(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            from utils.database import get_all_game_sources, init_database
            
            await init_database()
            
            custom_sources = await get_all_game_sources()
            
            embed = discord.Embed(
                title="Game Source URLs",
                color=0x3498DB
            )
            
            game_names = {
                'ps99': 'Pet Simulator 99',
                'gag': 'Grow a Garden',
                'am': 'Adopt Me',
                'bf': 'Blox Fruits',
                'sab': 'Steal a Brainrot'
            }
            
            for game_code, adapter in APIRegistry.all().items():
                game_name = game_names.get(game_code, game_code.upper())
                default_url = getattr(adapter, 'default_values_url', adapter.values_url)
                custom_url = custom_sources.get(game_code)
                
                if custom_url:
                    value = f"**Custom:** {custom_url}\nDefault: {default_url}"
                else:
                    value = f"**Default:** {default_url}"
                
                embed.add_field(name=game_name, value=value, inline=False)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")
    
    @owner_group.command(name="reset_source", description="Reset a game to its default scraping URL")
    @is_owner()
    @app_commands.describe(game="The game to reset to default URL")
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    async def reset_source(self, interaction: discord.Interaction, game: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            from utils.database import get_db, init_database
            
            await init_database()
            
            db = await get_db()
            await db.execute('DELETE FROM game_sources WHERE game = ?', (game,))
            await db.commit()
            await db.close()
            
            adapter = APIRegistry.get(game)
            if adapter:
                adapter._cache.clear()
                adapter._cache_expiry.clear()
                default_url = getattr(adapter, 'default_values_url', adapter.values_url)
                adapter.values_url = default_url
                
                items = await adapter.fetch_items()
                item_count = len(items) if items else 0
                
                await interaction.followup.send(
                    f"✅ Reset **{game.upper()}** to default URL\n"
                    f"URL: {default_url}\n"
                    f"Fetched: {item_count} items"
                )
            else:
                await interaction.followup.send(f"❌ Game '{game}' not found")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")
    
    @owner_group.command(name="init_db", description="Initialize/reset database")
    @is_owner()
    async def initialize_db(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            await init_database()
            await interaction.followup.send("Database initialized successfully.")
        except Exception as e:
            await interaction.followup.send(f"Failed to initialize database: {e}")
    
    @owner_group.command(name="shutdown", description="Shutdown the bot")
    @is_owner()
    async def shutdown(self, interaction: discord.Interaction):
        await interaction.response.send_message("Shutting down...", ephemeral=True)
        await self.bot.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(OwnerCog(bot))
