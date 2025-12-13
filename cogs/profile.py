import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import aiohttp

from utils.database import get_user, create_user, update_user
from utils.trust_engine import trust_engine
from utils.validators import Validators
from ui.embeds import ProfileEmbed
from ui.modals import LinkRobloxModal

class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="profile", description="View trading profile")
    @app_commands.describe(user="The user to view (defaults to yourself)")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        target = user or interaction.user
        
        profile_data = await get_user(target.id)
        
        if not profile_data:
            if target == interaction.user:
                profile_data = await create_user(target.id, str(target.created_at))
            else:
                await interaction.response.send_message(
                    f"{target.display_name} hasn't set up their trading profile yet.",
                    ephemeral=True
                )
                return
        
        discord_age = (discord.utils.utcnow() - target.created_at).days
        profile_data['discord_age_days'] = discord_age
        
        trust_score = trust_engine.calculate_trust_score(profile_data)
        tier = trust_engine.get_trust_tier(trust_score)
        
        profile_data['trust_score'] = trust_score
        profile_data['trust_tier'] = tier.value
        
        embed = ProfileEmbed.create(target, profile_data)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="link_roblox", description="Link your Roblox account")
    async def link_roblox(self, interaction: discord.Interaction):
        modal = LinkRobloxModal()
        await interaction.response.send_modal(modal)
        
        await modal.wait()
        
        if not modal.username_value:
            return
        
        username = modal.username_value
        
        valid, error = Validators.validate_roblox_username(username)
        if not valid:
            await interaction.followup.send(f"Invalid username: {error}", ephemeral=True)
            return
        
        roblox_data = await self._fetch_roblox_user(username)
        
        if not roblox_data:
            await interaction.followup.send(
                f"Could not find Roblox user '{username}'. Please check the spelling.",
                ephemeral=True
            )
            return
        
        user = await get_user(interaction.user.id)
        if not user:
            user = await create_user(interaction.user.id, str(interaction.user.created_at))
        
        await update_user(
            interaction.user.id,
            roblox_username=roblox_data['name'],
            roblox_id=roblox_data['id'],
            roblox_account_age=roblox_data.get('age_days', 0)
        )
        
        embed = discord.Embed(
            title="Roblox Account Linked",
            description=f"Successfully linked to **{roblox_data['name']}**",
            color=0x2ECC71
        )
        
        embed.add_field(name="Roblox ID", value=str(roblox_data['id']), inline=True)
        embed.add_field(name="Account Age", value=f"{roblox_data.get('age_days', 0)} days", inline=True)
        
        await interaction.followup.send(embed=embed)
    
    async def _fetch_roblox_user(self, username: str) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://users.roblox.com/v1/usernames/users',
                    json={'usernames': [username], 'excludeBannedUsers': True}
                ) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    if not data.get('data'):
                        return None
                    
                    user_data = data['data'][0]
                    user_id = user_data['id']
                
                async with session.get(f'https://users.roblox.com/v1/users/{user_id}') as response:
                    if response.status != 200:
                        return {'id': user_id, 'name': user_data['name'], 'age_days': 0}
                    
                    details = await response.json()
                    
                    created = details.get('created', '')
                    age_days = 0
                    if created:
                        from datetime import datetime
                        try:
                            created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                            age_days = (datetime.now(created_date.tzinfo) - created_date).days
                        except:
                            pass
                    
                    return {
                        'id': user_id,
                        'name': details.get('name', user_data['name']),
                        'display_name': details.get('displayName', ''),
                        'age_days': age_days
                    }
        except Exception as e:
            print(f"Error fetching Roblox user: {e}")
            return None
    
    @app_commands.command(name="unlink_roblox", description="Unlink your Roblox account")
    async def unlink_roblox(self, interaction: discord.Interaction):
        user = await get_user(interaction.user.id)
        
        if not user or not user.get('roblox_username'):
            await interaction.response.send_message("You don't have a linked Roblox account.", ephemeral=True)
            return
        
        await update_user(
            interaction.user.id,
            roblox_username=None,
            roblox_id=None,
            roblox_account_age=None
        )
        
        await interaction.response.send_message("Roblox account unlinked.", ephemeral=True)
    
    @app_commands.command(name="stats", description="View your trading statistics")
    async def stats(self, interaction: discord.Interaction):
        user = await get_user(interaction.user.id)
        
        if not user:
            await interaction.response.send_message(
                "You haven't made any trades yet.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Trading Statistics",
            color=0x3498DB
        )
        
        total = user.get('total_trades', 0)
        successful = user.get('successful_trades', 0)
        disputed = user.get('disputed_trades', 0)
        cancelled = user.get('cancelled_trades', 0)
        
        embed.add_field(name="Total Trades", value=str(total), inline=True)
        embed.add_field(name="Successful", value=str(successful), inline=True)
        embed.add_field(name="Disputed", value=str(disputed), inline=True)
        
        if total > 0:
            success_rate = (successful / total) * 100
            embed.add_field(name="Success Rate", value=f"{success_rate:.1f}%", inline=True)
        
        embed.add_field(name="Cancelled", value=str(cancelled), inline=True)
        
        total_value = user.get('total_value_traded', 0)
        embed.add_field(name="Total Value Traded", value=f"{total_value:,.0f}", inline=True)
        
        embed.add_field(
            name="Reputation Scores",
            value=f"Reliability: {user.get('reliability', 50):.0f}\n"
                  f"Fairness: {user.get('fairness', 50):.0f}\n"
                  f"Responsiveness: {user.get('responsiveness', 50):.0f}\n"
                  f"Proof Compliance: {user.get('proof_compliance', 50):.0f}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
