import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json
import os

from api.base import APIRegistry
from utils.database import init_database

class OwnerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def is_owner():
        async def predicate(interaction: discord.Interaction) -> bool:
            return await interaction.client.is_owner(interaction.user)
        return app_commands.check(predicate)
    
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
            self.bot.tree.copy_global_to(guild=interaction.guild)
            synced = await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send(f"Synced {len(synced)} commands to this guild.")
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
        embed.add_field(name="Users", value=str(sum(g.member_count for g in self.bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{self.bot.latency*1000:.0f}ms", inline=True)
        
        cogs_loaded = list(self.bot.cogs.keys())
        embed.add_field(name="Cogs Loaded", value=", ".join(cogs_loaded) or "None", inline=False)
        
        api_status = await APIRegistry.health_check_all()
        api_text = "\n".join([f"{'✅' if v else '❌'} {k.upper()}" for k, v in api_status.items()])
        embed.add_field(name="API Status", value=api_text or "No APIs", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @owner_group.command(name="refresh_cache", description="Refresh all item caches")
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
                    refreshed.append(f"✅ {game.upper()}: {len(items)} items")
                else:
                    refreshed.append(f"⚠️ {game.upper()}: No items (using fallback)")
            except Exception as e:
                refreshed.append(f"❌ {game.upper()}: {str(e)[:50]}")
        
        await interaction.followup.send("\n".join(refreshed))
    
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
