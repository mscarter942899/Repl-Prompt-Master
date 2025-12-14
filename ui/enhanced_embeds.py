import discord
from typing import Dict, List, Optional
from datetime import datetime
import json

from ui.embeds import GAME_COLORS, GAME_NAMES, TIER_EMOJIS
from ui.trade_builder import RARITY_EMOJIS, format_value
from ui.constants import DIAMONDS_EMOJI


class EnhancedTradeEmbed:
    @staticmethod
    def create_visual_trade(trade: Dict, requester: discord.User, 
                            target: Optional[discord.User] = None) -> discord.Embed:
        game = trade.get('game', 'unknown')
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(
            title=f"🔄 Trade Offer - {GAME_NAMES.get(game, game.upper())}",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        embed.set_author(
            name=f"From: {requester.display_name}",
            icon_url=requester.display_avatar.url
        )
        
        req_items = trade.get('requester_items', '[]')
        if isinstance(req_items, str):
            try:
                req_items = json.loads(req_items)
            except:
                req_items = []
        
        offering_lines = []
        total_offering = 0
        first_icon = None
        
        for item in req_items:
            if isinstance(item, dict):
                emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
                name = item.get('name', 'Unknown')
                value = item.get('value', 0)
                qty = item.get('quantity', 1)
                
                total_offering += value * qty
                line = f"{emoji} **{name}**"
                if qty > 1:
                    line += f" x{qty}"
                if value > 0:
                    line += f" `{format_value(value)}`"
                offering_lines.append(line)
                
                if not first_icon and item.get('icon_url'):
                    first_icon = item['icon_url']
        
        offering_gems = trade.get('offering_gems', 0)
        if offering_gems > 0:
            offering_lines.append(f"{DIAMONDS_EMOJI} **{format_value(offering_gems)} Diamonds**")
            total_offering += offering_gems
        
        if offering_lines:
            offering_text = "\n".join(offering_lines[:12])
            if len(offering_lines) > 12:
                offering_text += f"\n*+{len(offering_lines) - 12} more items*"
            embed.add_field(
                name=f"📦 Offering ({len(req_items)} items)",
                value=offering_text,
                inline=True
            )
        else:
            embed.add_field(name="📦 Offering", value="*No items*", inline=True)
        
        tgt_items = trade.get('target_items', '[]')
        if isinstance(tgt_items, str):
            try:
                tgt_items = json.loads(tgt_items)
            except:
                tgt_items = []
        
        requesting_lines = []
        total_requesting = 0
        
        for item in tgt_items:
            if isinstance(item, dict):
                emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
                name = item.get('name', 'Unknown')
                value = item.get('value', 0)
                qty = item.get('quantity', 1)
                
                total_requesting += value * qty
                line = f"{emoji} **{name}**"
                if qty > 1:
                    line += f" x{qty}"
                if value > 0:
                    line += f" `{format_value(value)}`"
                requesting_lines.append(line)
        
        requesting_gems = trade.get('requesting_gems', 0)
        if requesting_gems > 0:
            requesting_lines.append(f"{DIAMONDS_EMOJI} **{format_value(requesting_gems)} Diamonds**")
            total_requesting += requesting_gems
        
        if requesting_lines:
            requesting_text = "\n".join(requesting_lines[:12])
            if len(requesting_lines) > 12:
                requesting_text += f"\n*+{len(requesting_lines) - 12} more items*"
            embed.add_field(
                name=f"🎯 Requesting ({len(tgt_items)} items)",
                value=requesting_text,
                inline=True
            )
        else:
            embed.add_field(name="🎯 Requesting", value="*Open to offers*", inline=True)
        
        if first_icon:
            embed.set_thumbnail(url=first_icon)
        
        if total_offering > 0 or total_requesting > 0:
            diff = total_offering - total_requesting
            if diff > 0:
                analysis = f"📈 Overpaying by **{format_value(abs(diff))}**"
            elif diff < 0:
                analysis = f"📉 Underpaying by **{format_value(abs(diff))}**"
            else:
                analysis = "⚖️ **Fair trade!**"
            
            value_text = f"Offer: `{format_value(total_offering)}` vs Request: `{format_value(total_requesting)}`\n{analysis}"
            embed.add_field(name="💰 Trade Value", value=value_text, inline=False)
        
        notes = trade.get('notes', '')
        if notes:
            embed.add_field(name="📝 Notes", value=notes[:200], inline=False)
        
        status_info = {
            'draft': ('📝', 'Draft', 0x95A5A6),
            'pending': ('⏳', 'Pending', 0xF39C12),
            'accepted': ('✅', 'Accepted', 0x2ECC71),
            'locked': ('🔒', 'Locked - Both Ready', 0x9B59B6),
            'in_game_trade': ('🎮', 'In-Game Trade', 0x3498DB),
            'completed': ('✨', 'Completed', 0x2ECC71),
            'disputed': ('⚠️', 'Disputed', 0xE74C3C),
            'cancelled': ('❌', 'Cancelled', 0x95A5A6)
        }
        
        status = trade.get('status', 'draft')
        status_emoji, status_text, _ = status_info.get(status, ('❓', status.title(), 0x95A5A6))
        
        lock_status = ""
        if trade.get('requester_locked') and trade.get('target_locked'):
            lock_status = " | 🔒 Both Locked"
        elif trade.get('requester_locked'):
            lock_status = " | 🔓 Requester Locked"
        elif trade.get('target_locked'):
            lock_status = " | 🔓 Target Locked"
        
        embed.add_field(
            name="Status",
            value=f"{status_emoji} {status_text}{lock_status}",
            inline=True
        )
        
        if target:
            embed.add_field(name="Trading With", value=target.mention, inline=True)
        
        embed.set_footer(text=f"Trade ID: #{trade.get('id', 'N/A')}")
        
        return embed
    
    @staticmethod
    def create_trade_feed_entry(trade: Dict, requester: discord.User, 
                                 target: discord.User) -> discord.Embed:
        game = trade.get('game', 'unknown')
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(
            title=f"✅ Trade Completed - {GAME_NAMES.get(game, game.upper())}",
            color=0x2ECC71,
            timestamp=datetime.utcnow()
        )
        
        embed.set_author(
            name="Trade Feed",
            icon_url="https://cdn.discordapp.com/emojis/1234567890.png"
        )
        
        req_items = trade.get('requester_items', '[]')
        if isinstance(req_items, str):
            try:
                req_items = json.loads(req_items)
            except:
                req_items = []
        
        tgt_items = trade.get('target_items', '[]')
        if isinstance(tgt_items, str):
            try:
                tgt_items = json.loads(tgt_items)
            except:
                tgt_items = []
        
        first_icon = None
        
        req_summary = []
        for item in req_items[:5]:
            if isinstance(item, dict):
                emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
                req_summary.append(f"{emoji} {item.get('name', 'Unknown')}")
                if not first_icon and item.get('icon_url'):
                    first_icon = item['icon_url']
        
        offering_gems = trade.get('offering_gems', 0)
        if offering_gems > 0:
            req_summary.append(f"{DIAMONDS_EMOJI} {format_value(offering_gems)}")
        
        if len(req_items) > 5:
            req_summary.append(f"*+{len(req_items) - 5} more*")
        
        tgt_summary = []
        for item in tgt_items[:5]:
            if isinstance(item, dict):
                emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
                tgt_summary.append(f"{emoji} {item.get('name', 'Unknown')}")
        
        requesting_gems = trade.get('requesting_gems', 0)
        if requesting_gems > 0:
            tgt_summary.append(f"{DIAMONDS_EMOJI} {format_value(requesting_gems)}")
        
        if len(tgt_items) > 5:
            tgt_summary.append(f"*+{len(tgt_items) - 5} more*")
        
        embed.add_field(
            name=f"📦 {requester.display_name} gave",
            value="\n".join(req_summary) if req_summary else "*Unknown*",
            inline=True
        )
        
        embed.add_field(
            name=f"🎯 {target.display_name} gave",
            value="\n".join(tgt_summary) if tgt_summary else "*Unknown*",
            inline=True
        )
        
        if first_icon:
            embed.set_thumbnail(url=first_icon)
        
        embed.set_footer(text=f"Trade #{trade.get('id', 'N/A')}")
        
        return embed


class WishlistEmbed:
    @staticmethod
    def create(user: discord.User, items: List[Dict], game: str) -> discord.Embed:
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(
            title=f"📋 {user.display_name}'s Wishlist - {GAME_NAMES.get(game, game.upper())}",
            color=color
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        if not items:
            embed.description = "No items in wishlist for this game."
            return embed
        
        lines = []
        for i, item in enumerate(items[:20], 1):
            priority_emoji = "🔥" if item.get('priority', 1) >= 3 else "⭐" if item.get('priority', 1) >= 2 else "📌"
            max_price = item.get('max_price')
            price_text = f" (max: {format_value(max_price)})" if max_price else ""
            lines.append(f"{priority_emoji} **{item.get('item_name', 'Unknown')}**{price_text}")
        
        embed.description = "\n".join(lines)
        
        if len(items) > 20:
            embed.set_footer(text=f"Showing 20 of {len(items)} items")
        else:
            embed.set_footer(text=f"{len(items)} items in wishlist")
        
        return embed


class LeaderboardEmbed:
    @staticmethod
    def create(bot, leaders: List[Dict], metric: str = "total_trades") -> discord.Embed:
        metric_names = {
            'total_trades': '🏆 Top Traders by Volume',
            'successful_trades': '✅ Most Successful Traders',
            'trust_score': '💎 Highest Trust Scores',
            'total_value_traded': '💰 Highest Value Traders'
        }
        
        embed = discord.Embed(
            title=metric_names.get(metric, "🏆 Trade Leaderboard"),
            color=0xFFD700,
            timestamp=datetime.utcnow()
        )
        
        if not leaders:
            embed.description = "No traders found yet!"
            return embed
        
        lines = []
        medals = ['🥇', '🥈', '🥉']
        
        for i, leader in enumerate(leaders, 1):
            medal = medals[i-1] if i <= 3 else f"**{i}.**"
            tier_emoji = TIER_EMOJIS.get(leader.get('trust_tier', 'Bronze'), '🔰')
            
            if metric == 'total_trades':
                stat = f"{leader.get('total_trades', 0)} trades"
            elif metric == 'successful_trades':
                stat = f"{leader.get('successful_trades', 0)} successful"
            elif metric == 'trust_score':
                stat = f"{leader.get('trust_score', 0):.1f}/100"
            else:
                stat = format_value(leader.get('total_value_traded', 0))
            
            lines.append(f"{medal} <@{leader['discord_id']}> {tier_emoji} - {stat}")
        
        embed.description = "\n".join(lines)
        embed.set_footer(text="Updated live")
        
        return embed


class LFFTEmbed:
    @staticmethod
    def create_post(post: Dict, user: discord.User) -> discord.Embed:
        game = post.get('game', 'unknown')
        post_type = post.get('post_type', 'ft')
        color = GAME_COLORS.get(game, 0x7289DA)
        
        type_info = {
            'lf': ('🔍 Looking For', 0x3498DB),
            'ft': ('📦 For Trade', 0x2ECC71)
        }
        
        title, type_color = type_info.get(post_type, ('📋 Trade Post', color))
        
        embed = discord.Embed(
            title=f"{title} - {GAME_NAMES.get(game, game.upper())}",
            color=type_color,
            timestamp=datetime.utcnow()
        )
        
        embed.set_author(
            name=user.display_name,
            icon_url=user.display_avatar.url
        )
        
        items = post.get('items', [])
        if items:
            lines = []
            for item in items[:15]:
                if isinstance(item, dict):
                    emoji = RARITY_EMOJIS.get(item.get('rarity', 'Common'), '⚪')
                    lines.append(f"{emoji} **{item.get('name', 'Unknown')}**")
                else:
                    lines.append(f"• {item}")
            
            embed.add_field(
                name="Items",
                value="\n".join(lines),
                inline=True
            )
        
        gems = post.get('gems', 0)
        if gems > 0:
            gem_action = "Offering" if post_type == 'ft' else "Want"
            embed.add_field(
                name=f"{DIAMONDS_EMOJI} {gem_action}",
                value=f"**{format_value(gems)}** Diamonds",
                inline=True
            )
        
        notes = post.get('notes', '')
        if notes:
            embed.add_field(name="📝 Notes", value=notes[:200], inline=False)
        
        embed.set_footer(text=f"Post #{post.get('id', 'N/A')} | Click to respond")
        
        return embed
