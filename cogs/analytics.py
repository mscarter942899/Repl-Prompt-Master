import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, timedelta

from utils.database import DATABASE_PATH

class AnalyticsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="server_stats", description="View server trading statistics")
    async def server_stats(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute('SELECT COUNT(*) FROM trades') as cursor:
                total_trades = (await cursor.fetchone())[0]
            
            async with db.execute("SELECT COUNT(*) FROM trades WHERE status = 'completed'") as cursor:
                completed_trades = (await cursor.fetchone())[0]
            
            async with db.execute("SELECT COUNT(*) FROM trades WHERE status = 'disputed'") as cursor:
                disputed_trades = (await cursor.fetchone())[0]
            
            async with db.execute('SELECT COUNT(DISTINCT requester_id) FROM trades') as cursor:
                unique_traders = (await cursor.fetchone())[0]
            
            async with db.execute('SELECT game, COUNT(*) as count FROM trades GROUP BY game ORDER BY count DESC') as cursor:
                game_stats = await cursor.fetchall()
        
        embed = discord.Embed(
            title="Server Trading Statistics",
            color=0x3498DB,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Total Trades", value=str(total_trades), inline=True)
        embed.add_field(name="Completed", value=str(completed_trades), inline=True)
        embed.add_field(name="Disputed", value=str(disputed_trades), inline=True)
        
        if total_trades > 0:
            success_rate = (completed_trades / total_trades) * 100
            embed.add_field(name="Success Rate", value=f"{success_rate:.1f}%", inline=True)
            
            scam_prevention = ((total_trades - disputed_trades) / total_trades) * 100
            embed.add_field(name="Safe Trade Rate", value=f"{scam_prevention:.1f}%", inline=True)
        
        embed.add_field(name="Unique Traders", value=str(unique_traders), inline=True)
        
        if game_stats:
            game_text = "\n".join([f"{row[0].upper()}: {row[1]} trades" for row in game_stats[:5]])
            embed.add_field(name="Trades by Game", value=game_text, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="leaderboard", description="View top traders")
    @app_commands.describe(metric="What to rank by")
    @app_commands.choices(metric=[
        app_commands.Choice(name="Total Trades", value="total_trades"),
        app_commands.Choice(name="Successful Trades", value="successful_trades"),
        app_commands.Choice(name="Trust Score", value="trust_score"),
        app_commands.Choice(name="Total Value Traded", value="total_value_traded")
    ])
    async def leaderboard(self, interaction: discord.Interaction, metric: str = "total_trades"):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(f'''
                SELECT discord_id, {metric}, trust_tier 
                FROM users 
                WHERE is_banned = 0 AND {metric} > 0
                ORDER BY {metric} DESC 
                LIMIT 10
            ''') as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            await interaction.response.send_message("No data available yet.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Trading Leaderboard - {metric.replace('_', ' ').title()}",
            color=0xFFD700
        )
        
        leaderboard_text = []
        medals = ['🥇', '🥈', '🥉']
        
        for i, row in enumerate(rows):
            try:
                user = await self.bot.fetch_user(row['discord_id'])
                name = user.display_name
            except:
                name = f"User {row['discord_id']}"
            
            medal = medals[i] if i < 3 else f"{i+1}."
            value = row[metric]
            
            if metric == 'total_value_traded':
                value_str = f"{value:,.0f}"
            elif metric == 'trust_score':
                value_str = f"{value:.1f}/100"
            else:
                value_str = str(value)
            
            leaderboard_text.append(f"{medal} **{name}** - {value_str}")
        
        embed.description = "\n".join(leaderboard_text)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="activity", description="View recent trading activity")
    async def activity(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute('''
                SELECT * FROM trades 
                ORDER BY updated_at DESC 
                LIMIT 10
            ''') as cursor:
                recent_trades = await cursor.fetchall()
            
            today = datetime.utcnow().date().isoformat()
            async with db.execute(f'''
                SELECT COUNT(*) FROM trades 
                WHERE DATE(created_at) = ?
            ''', (today,)) as cursor:
                today_count = (await cursor.fetchone())[0]
        
        embed = discord.Embed(
            title="Recent Trading Activity",
            color=0x2ECC71,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Trades Today", value=str(today_count), inline=True)
        
        if recent_trades:
            activity_text = []
            for trade in recent_trades[:5]:
                status_emoji = {
                    'completed': '✅',
                    'pending': '⏳',
                    'disputed': '⚠️',
                    'cancelled': '❌'
                }.get(trade['status'], '❓')
                
                activity_text.append(
                    f"{status_emoji} Trade #{trade['id']} ({trade['game'].upper()}) - {trade['status']}"
                )
            
            embed.add_field(
                name="Recent Trades",
                value="\n".join(activity_text),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyticsCog(bot))
