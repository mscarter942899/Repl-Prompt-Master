import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json

from utils.database import (
    get_user, update_user, get_trade, update_trade,
    add_trade_history, log_audit
)
from utils.trust_engine import trust_engine

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def is_moderator():
        async def predicate(interaction: discord.Interaction) -> bool:
            if not interaction.guild:
                return False
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                return False
            return member.guild_permissions.moderate_members or member.guild_permissions.administrator
        return app_commands.check(predicate)
    
    mod_group = app_commands.Group(name="mod", description="Moderation commands")
    
    @mod_group.command(name="audit_trade", description="View detailed trade audit log")
    @is_moderator()
    @app_commands.describe(trade_id="The trade ID to audit")
    async def audit_trade(self, interaction: discord.Interaction, trade_id: int):
        trade = await get_trade(trade_id)
        
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Trade Audit - #{trade_id}",
            color=0x9B59B6
        )
        
        requester = await self.bot.fetch_user(trade['requester_id'])
        target = await self.bot.fetch_user(trade['target_id']) if trade['target_id'] else None
        
        embed.add_field(name="Requester", value=f"{requester.mention} ({requester.id})", inline=True)
        embed.add_field(name="Target", value=f"{target.mention if target else 'N/A'} ({trade['target_id'] or 'N/A'})", inline=True)
        embed.add_field(name="Game", value=trade['game'].upper(), inline=True)
        embed.add_field(name="Status", value=trade['status'], inline=True)
        embed.add_field(name="Risk Level", value=trade.get('risk_level', 'Unknown'), inline=True)
        embed.add_field(name="Created", value=trade['created_at'], inline=True)
        
        if trade.get('receipt_hash'):
            embed.add_field(name="Receipt Hash", value=f"`{trade['receipt_hash'][:32]}...`", inline=False)
        
        req_items = trade.get('requester_items', '[]')
        if isinstance(req_items, str):
            try:
                req_items = json.loads(req_items)
            except:
                req_items = []
        
        items_text = ', '.join([i.get('name', str(i)) if isinstance(i, dict) else str(i) for i in req_items])
        embed.add_field(name="Offered Items", value=items_text or "None", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @mod_group.command(name="force_resolve", description="Force resolve a disputed trade")
    @is_moderator()
    @app_commands.describe(
        trade_id="The trade ID to resolve",
        resolution="The resolution outcome"
    )
    @app_commands.choices(resolution=[
        app_commands.Choice(name="Complete - Both parties satisfied", value="completed"),
        app_commands.Choice(name="Cancelled - No fault", value="cancelled"),
        app_commands.Choice(name="Requester at fault", value="requester_fault"),
        app_commands.Choice(name="Target at fault", value="target_fault")
    ])
    async def force_resolve(self, interaction: discord.Interaction, trade_id: int, resolution: str):
        trade = await get_trade(trade_id)
        
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        if trade['status'] != 'disputed':
            await interaction.response.send_message("Only disputed trades can be force resolved.", ephemeral=True)
            return
        
        if resolution == 'completed':
            await update_trade(trade_id, status='completed')
            
            if trade['requester_id']:
                req_data = await get_user(trade['requester_id'])
                if req_data:
                    updates = trust_engine.update_reputation(req_data, 'trade_completed')
                    await update_user(trade['requester_id'], **updates)
            
            if trade['target_id']:
                tgt_data = await get_user(trade['target_id'])
                if tgt_data:
                    updates = trust_engine.update_reputation(tgt_data, 'trade_completed')
                    await update_user(trade['target_id'], **updates)
                    
        elif resolution == 'cancelled':
            await update_trade(trade_id, status='cancelled')
            
        elif resolution == 'requester_fault':
            await update_trade(trade_id, status='cancelled')
            if trade['requester_id']:
                req_data = await get_user(trade['requester_id'])
                if req_data:
                    updates = trust_engine.update_reputation(req_data, 'scam_detected')
                    await update_user(trade['requester_id'], **updates)
                    
        elif resolution == 'target_fault':
            await update_trade(trade_id, status='cancelled')
            if trade['target_id']:
                tgt_data = await get_user(trade['target_id'])
                if tgt_data:
                    updates = trust_engine.update_reputation(tgt_data, 'scam_detected')
                    await update_user(trade['target_id'], **updates)
        
        await add_trade_history(trade_id, f'force_resolved_{resolution}', interaction.user.id)
        await log_audit('force_resolve', interaction.user.id, trade_id, resolution)
        
        await interaction.response.send_message(
            f"Trade #{trade_id} has been resolved as: {resolution}",
            ephemeral=True
        )
    
    @mod_group.command(name="ban_user", description="Ban a user from trading")
    @is_moderator()
    @app_commands.describe(
        user="The user to ban",
        reason="Reason for the ban"
    )
    async def ban_user(self, interaction: discord.Interaction, user: discord.User, reason: str):
        await update_user(user.id, is_banned=1, ban_reason=reason)
        await log_audit('user_banned', interaction.user.id, user.id, reason)
        
        await interaction.response.send_message(
            f"{user.mention} has been banned from trading.\nReason: {reason}",
            ephemeral=True
        )
    
    @mod_group.command(name="unban_user", description="Unban a user from trading")
    @is_moderator()
    @app_commands.describe(user="The user to unban")
    async def unban_user(self, interaction: discord.Interaction, user: discord.User):
        await update_user(user.id, is_banned=0, ban_reason=None)
        await log_audit('user_unbanned', interaction.user.id, user.id, None)
        
        await interaction.response.send_message(
            f"{user.mention} has been unbanned from trading.",
            ephemeral=True
        )
    
    @mod_group.command(name="rollback_rep", description="Rollback a user's reputation to default")
    @is_moderator()
    @app_commands.describe(user="The user to reset")
    async def rollback_rep(self, interaction: discord.Interaction, user: discord.User):
        await update_user(
            user.id,
            trust_score=50.0,
            trust_tier='Bronze',
            reliability=50.0,
            fairness=50.0,
            responsiveness=50.0,
            proof_compliance=50.0
        )
        
        await log_audit('reputation_reset', interaction.user.id, user.id, 'Manual reset by moderator')
        
        await interaction.response.send_message(
            f"{user.mention}'s reputation has been reset to default.",
            ephemeral=True
        )
    
    @mod_group.command(name="flag_user", description="Flag a user for review")
    @is_moderator()
    @app_commands.describe(
        user="The user to flag",
        reason="Reason for flagging"
    )
    async def flag_user(self, interaction: discord.Interaction, user: discord.User, reason: str):
        await log_audit('user_flagged', interaction.user.id, user.id, reason)
        
        await interaction.response.send_message(
            f"{user.mention} has been flagged for review.\nReason: {reason}",
            ephemeral=True
        )
    
    @mod_group.command(name="view_reports", description="View pending reports")
    @is_moderator()
    async def view_reports(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Report viewing functionality coming soon.",
            ephemeral=True
        )
    
    @mod_group.command(name="replay_trade", description="View visual timeline of a trade")
    @is_moderator()
    @app_commands.describe(trade_id="The trade ID to replay")
    async def replay_trade(self, interaction: discord.Interaction, trade_id: int):
        import aiosqlite
        from utils.database import DATABASE_PATH
        
        trade = await get_trade(trade_id)
        
        if not trade:
            await interaction.response.send_message("Trade not found.", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM trade_history WHERE trade_id = ? ORDER BY timestamp ASC",
                (trade_id,)
            ) as cursor:
                history = await cursor.fetchall()
        
        embed = discord.Embed(
            title=f"Trade Timeline - #{trade_id}",
            color=0x9B59B6
        )
        
        requester = await self.bot.fetch_user(trade['requester_id'])
        target = None
        if trade['target_id']:
            try:
                target = await self.bot.fetch_user(trade['target_id'])
            except:
                pass
        
        embed.add_field(
            name="Participants",
            value=f"Requester: {requester.mention}\nTarget: {target.mention if target else 'N/A'}",
            inline=False
        )
        
        embed.add_field(name="Game", value=trade['game'].upper(), inline=True)
        embed.add_field(name="Final Status", value=trade['status'].replace('_', ' ').title(), inline=True)
        embed.add_field(name="Risk Level", value=trade.get('risk_level', 'Unknown'), inline=True)
        
        if history:
            timeline_text = []
            action_emojis = {
                'created': '📝',
                'accepted': '✅',
                'declined': '❌',
                'cancelled': '🚫',
                'trust_check': '🔍',
                'handoff_started': '🎮',
                'completed': '✨',
                'disputed': '⚠️',
                'expired': '⏰',
                'force_resolved': '⚖️'
            }
            
            for event in history:
                action = event['action']
                emoji = action_emojis.get(action.split('_')[0], '📋')
                timestamp = event['timestamp'][:16] if event['timestamp'] else 'Unknown'
                
                actor_text = ""
                if event['actor_id'] and event['actor_id'] != 0:
                    try:
                        actor = await self.bot.fetch_user(event['actor_id'])
                        actor_text = f" by {actor.display_name}"
                    except:
                        actor_text = f" by User {event['actor_id']}"
                
                timeline_text.append(f"{emoji} **{action.replace('_', ' ').title()}**{actor_text}\n   `{timestamp}`")
            
            timeline_display = "\n".join(timeline_text[:15])
            if len(timeline_text) > 15:
                timeline_display += f"\n... and {len(timeline_text) - 15} more events"
            
            embed.add_field(name="Timeline", value=timeline_display, inline=False)
        else:
            embed.add_field(name="Timeline", value="No events recorded", inline=False)
        
        if trade.get('receipt_hash'):
            embed.add_field(
                name="Receipt Hash",
                value=f"`{trade['receipt_hash'][:32]}...`",
                inline=False
            )
        
        embed.set_footer(text=f"Created: {trade['created_at'][:16]}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
