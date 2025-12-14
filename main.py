import discord
from discord.ext import commands
import asyncio
import os
import logging
from dotenv import load_dotenv

from keep_alive import keep_alive
from utils.database import init_database, get_item_count, populate_from_fallback
from api import setup_all_adapters

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('RobloxTradingBot')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class RobloxTradingBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        self.initial_extensions = [
            'cogs.trading',
            'cogs.inventory',
            'cogs.profile',
            'cogs.search',
            'cogs.auctions',
            'cogs.moderation',
            'cogs.analytics',
            'cogs.owner',
            'cogs.item_manage',
            'cogs.settings'
        ]
    
    async def setup_hook(self):
        logger.info("Initializing database...")
        await init_database()
        
        item_count = await get_item_count()
        if item_count == 0:
            logger.info("Database empty, loading fallback data...")
            results = await populate_from_fallback()
            total = sum(results.values())
            logger.info(f"Loaded {total} items from fallback data")
        else:
            logger.info(f"Database has {item_count} items")
        
        logger.info("Setting up API adapters...")
        setup_all_adapters()
        
        logger.info("Loading cogs...")
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded {extension}")
            except Exception as e:
                logger.error(f"Failed to load {extension}: {e}")
        
        logger.info("Registering persistent views...")
        from ui.persistent_views import setup_persistent_views
        setup_persistent_views(self)
        
        logger.info("Syncing commands...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self):
        if self.user:
            logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="trades | /trade create"
            )
        )
    
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        logger.error(f"Command error: {error}")
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        if isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
        else:
            logger.error(f"App command error: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while processing your command.",
                    ephemeral=True
                )

async def main():
    keep_alive()
    
    bot = RobloxTradingBot()
    
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        logger.info("Please set your Discord bot token as DISCORD_TOKEN in the Secrets tab.")
        return
    
    try:
        await bot.start(token)
    except discord.LoginFailure:
        logger.error("Invalid Discord token provided!")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
