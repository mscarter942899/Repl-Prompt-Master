import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.database import get_guild_settings, set_guild_settings, set_trade_channel, set_game_trade_channel, get_all_game_trade_channels


def is_admin():
    """Check if user has administrator or manage_guild permissions."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        member = interaction.guild.get_member(interaction.user.id)
        if member:
            return member.guild_permissions.administrator or member.guild_permissions.manage_guild
        if hasattr(interaction.user, 'guild_permissions'):
            return interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild
        return False
    return app_commands.check(predicate)


class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    settings_group = app_commands.Group(name="settings", description="Server settings commands (Admin Only)")
    
    GAME_NAMES = {
        "ps99": "Pet Simulator 99",
        "gag": "Grow a Garden", 
        "am": "Adopt Me",
        "bf": "Blox Fruits",
        "sab": "Steal a Brainrot"
    }
    
    @settings_group.command(name="tradechannel", description="Set the channel where trade announcements are posted")
    @app_commands.describe(
        channel="The channel for trade announcements (leave empty to disable)",
        game="Set channel for a specific game (optional - if not set, applies to all games)"
    )
    @app_commands.choices(game=[
        app_commands.Choice(name="Pet Simulator 99", value="ps99"),
        app_commands.Choice(name="Grow a Garden", value="gag"),
        app_commands.Choice(name="Adopt Me", value="am"),
        app_commands.Choice(name="Blox Fruits", value="bf"),
        app_commands.Choice(name="Steal a Brainrot", value="sab")
    ])
    @app_commands.default_permissions(manage_guild=True)
    @is_admin()
    async def set_trade_channel_cmd(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None, game: Optional[str] = None):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        if channel:
            permissions = channel.permissions_for(interaction.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                await interaction.response.send_message(
                    f"I need **Send Messages** and **Embed Links** permissions in {channel.mention}!",
                    ephemeral=True
                )
                return
            
            if game:
                await set_game_trade_channel(interaction.guild.id, game, channel.id)
                game_name = self.GAME_NAMES.get(game, game)
                
                embed = discord.Embed(
                    title="Game Trade Channel Configured",
                    color=0x2ECC71,
                    description=f"**{game_name}** trades will now be posted to {channel.mention}"
                )
                embed.add_field(
                    name="What happens now?",
                    value=f"When users create trades for {game_name} without specifying a target, "
                          f"the trade will be announced in this channel!",
                    inline=False
                )
                embed.set_footer(text=f"Use /settings tradechannel game:{game} without a channel to disable")
            else:
                await set_trade_channel(interaction.guild.id, channel.id)
                
                embed = discord.Embed(
                    title="Default Trade Channel Configured",
                    color=0x2ECC71,
                    description=f"Trade announcements will now be posted to {channel.mention}"
                )
                embed.add_field(
                    name="What happens now?",
                    value="When users create trades without specifying a target, "
                          "the trade will be announced in this channel (unless a game-specific channel is set).",
                    inline=False
                )
                embed.set_footer(text="Use /settings tradechannel without a channel to disable")
            
            await interaction.response.send_message(embed=embed)
        else:
            if game:
                await set_game_trade_channel(interaction.guild.id, game, None)
                game_name = self.GAME_NAMES.get(game, game)
                await interaction.response.send_message(
                    f"Trade channel for **{game_name}** has been removed. Trades will use the default channel.",
                    ephemeral=True
                )
            else:
                await set_trade_channel(interaction.guild.id, None)
                await interaction.response.send_message(
                    "Default trade channel has been disabled. Trades will only be sent directly to users.",
                    ephemeral=True
                )
    
    @settings_group.command(name="view", description="View current server settings")
    @app_commands.default_permissions(manage_guild=True)
    @is_admin()
    async def view_settings(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        settings = await get_guild_settings(interaction.guild.id)
        
        embed = discord.Embed(
            title=f"Settings for {interaction.guild.name}",
            color=0x3498DB
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        
        if settings:
            trade_channel = None
            if settings.get('trade_channel_id'):
                trade_channel = interaction.guild.get_channel(settings['trade_channel_id'])
            
            log_channel = None
            if settings.get('log_channel_id'):
                log_channel = interaction.guild.get_channel(settings['log_channel_id'])
            
            mod_role = None
            if settings.get('mod_role_id'):
                mod_role = interaction.guild.get_role(settings['mod_role_id'])
            
            embed.add_field(
                name="Trade Announcements",
                value=trade_channel.mention if trade_channel else "Not configured",
                inline=True
            )
            embed.add_field(
                name="Log Channel",
                value=log_channel.mention if log_channel else "Not configured",
                inline=True
            )
            embed.add_field(
                name="Mod Role",
                value=mod_role.mention if mod_role else "Not configured",
                inline=True
            )
            embed.add_field(
                name="Announcements Enabled",
                value="Yes" if settings.get('announcement_enabled') else "No",
                inline=True
            )
            embed.add_field(
                name="Auto-Delete Expired",
                value="Yes" if settings.get('auto_delete_expired') else "No",
                inline=True
            )
            embed.add_field(
                name="Min Trust Score",
                value=f"{settings.get('min_trust_score', 0):.0f}",
                inline=True
            )
        else:
            embed.description = "No settings configured yet. Use the commands below to set up:"
            embed.add_field(
                name="Available Commands",
                value="`/settings tradechannel` - Set trade announcement channel\n"
                      "`/settings logchannel` - Set moderation log channel\n"
                      "`/settings modrole` - Set moderator role\n"
                      "`/settings toggle` - Toggle various features",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @settings_group.command(name="logchannel", description="Set the channel for moderation logs")
    @app_commands.describe(channel="The channel for logs (leave empty to disable)")
    @app_commands.default_permissions(manage_guild=True)
    @is_admin()
    async def set_log_channel(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        if channel:
            await set_guild_settings(interaction.guild.id, log_channel_id=channel.id)
            await interaction.response.send_message(
                f"Log channel set to {channel.mention}. Trade disputes and reports will be logged there.",
                ephemeral=True
            )
        else:
            await set_guild_settings(interaction.guild.id, log_channel_id=None)
            await interaction.response.send_message("Log channel disabled.", ephemeral=True)
    
    @settings_group.command(name="modrole", description="Set the moderator role for trade disputes")
    @app_commands.describe(role="The moderator role (leave empty to disable)")
    @app_commands.default_permissions(manage_guild=True)
    @is_admin()
    async def set_mod_role(self, interaction: discord.Interaction, role: Optional[discord.Role] = None):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        if role:
            await set_guild_settings(interaction.guild.id, mod_role_id=role.id)
            await interaction.response.send_message(
                f"Moderator role set to {role.mention}. They will be pinged for trade disputes.",
                ephemeral=True
            )
        else:
            await set_guild_settings(interaction.guild.id, mod_role_id=None)
            await interaction.response.send_message("Moderator role disabled.", ephemeral=True)
    
    @settings_group.command(name="toggle", description="Toggle server features on/off")
    @app_commands.describe(feature="The feature to toggle")
    @app_commands.choices(feature=[
        app_commands.Choice(name="Trade Announcements", value="announcement_enabled"),
        app_commands.Choice(name="Auto-Delete Expired Trades", value="auto_delete_expired"),
        app_commands.Choice(name="Require Verification", value="require_verification")
    ])
    @app_commands.default_permissions(manage_guild=True)
    @is_admin()
    async def toggle_feature(self, interaction: discord.Interaction, feature: str):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        settings = await get_guild_settings(interaction.guild.id)
        current_value = settings.get(feature, 1) if settings else 1
        new_value = 0 if current_value else 1
        
        await set_guild_settings(interaction.guild.id, **{feature: new_value})
        
        feature_names = {
            "announcement_enabled": "Trade Announcements",
            "auto_delete_expired": "Auto-Delete Expired Trades",
            "require_verification": "Require Verification"
        }
        
        status = "enabled" if new_value else "disabled"
        await interaction.response.send_message(
            f"**{feature_names.get(feature, feature)}** has been **{status}**.",
            ephemeral=True
        )
    
    @settings_group.command(name="tradefeed", description="Set channel for completed trade announcements")
    @app_commands.describe(channel="The channel for trade feed (leave empty to disable)")
    @app_commands.default_permissions(manage_guild=True)
    @is_admin()
    async def set_trade_feed(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        if channel:
            permissions = channel.permissions_for(interaction.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                await interaction.response.send_message(
                    f"I need **Send Messages** and **Embed Links** permissions in {channel.mention}!",
                    ephemeral=True
                )
                return
            
            await set_guild_settings(interaction.guild.id, trade_feed_channel_id=channel.id, trade_feed_enabled=1)
            
            embed = discord.Embed(
                title="📢 Trade Feed Configured!",
                color=0x2ECC71,
                description=f"Completed trades will now be announced in {channel.mention}"
            )
            embed.add_field(
                name="What gets posted?",
                value="• Completed trades with items traded\n"
                      "• Trade values and trader info\n"
                      "• Item images when available",
                inline=False
            )
            embed.set_footer(text="Use /settings toggle to enable/disable the feed")
            await interaction.response.send_message(embed=embed)
        else:
            await set_guild_settings(interaction.guild.id, trade_feed_channel_id=None, trade_feed_enabled=0)
            await interaction.response.send_message("Trade feed disabled.", ephemeral=True)
    
    @settings_group.command(name="mintrust", description="Set minimum trust score to create trades")
    @app_commands.describe(score="Minimum trust score (0-100, 0 to disable)")
    @app_commands.default_permissions(manage_guild=True)
    @is_admin()
    async def set_min_trust(self, interaction: discord.Interaction, score: int):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        if score < 0 or score > 100:
            await interaction.response.send_message("Score must be between 0 and 100.", ephemeral=True)
            return
        
        await set_guild_settings(interaction.guild.id, min_trust_score=float(score))
        
        if score > 0:
            await interaction.response.send_message(
                f"Minimum trust score set to **{score}**. Users below this score cannot create trades.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Minimum trust score requirement disabled. Anyone can create trades.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCog(bot))
