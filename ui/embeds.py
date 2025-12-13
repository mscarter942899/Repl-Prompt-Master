import discord
from typing import Dict, List, Optional
from datetime import datetime
from utils.trust_engine import RiskLevel, TrustTier

GAME_COLORS = {
    'ps99': 0x9B59B6,
    'gag': 0x2ECC71,
    'am': 0xE74C3C,
    'bf': 0x3498DB,
    'sab': 0xF39C12
}

GAME_NAMES = {
    'ps99': 'Pet Simulator 99',
    'gag': 'Grow a Garden',
    'am': 'Adopt Me',
    'bf': 'Blox Fruits',
    'sab': 'Steal a Brainrot'
}

TIER_EMOJIS = {
    'Bronze': '🥉',
    'Silver': '🥈',
    'Gold': '🥇',
    'Platinum': '💎',
    'Diamond': '👑'
}

RISK_COLORS = {
    RiskLevel.SAFE: 0x2ECC71,
    RiskLevel.CAUTION: 0xF39C12,
    RiskLevel.HIGH_RISK: 0xE74C3C
}


class TradeEmbed:
    @staticmethod
    def create_trade_offer(trade: Dict, requester: discord.User, target: Optional[discord.User] = None) -> discord.Embed:
        game = trade.get('game', 'unknown')
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(
            title=f"Trade Offer - {GAME_NAMES.get(game, game.upper())}",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        embed.set_author(name=f"From: {requester.display_name}", icon_url=requester.display_avatar.url)
        
        req_items = trade.get('requester_items', '[]')
        if isinstance(req_items, str):
            import json
            try:
                req_items = json.loads(req_items)
            except:
                req_items = []
        
        items_text = '\n'.join([f"• {item.get('name', item) if isinstance(item, dict) else item}" for item in req_items]) or "No items"
        embed.add_field(name="📦 Offering", value=items_text, inline=True)
        
        tgt_items = trade.get('target_items', '[]')
        if isinstance(tgt_items, str):
            import json
            try:
                tgt_items = json.loads(tgt_items)
            except:
                tgt_items = []
        
        if tgt_items:
            items_text = '\n'.join([f"• {item.get('name', item) if isinstance(item, dict) else item}" for item in tgt_items])
            embed.add_field(name="🎯 Requesting", value=items_text, inline=True)
        
        status_emoji = {
            'draft': '📝',
            'pending': '⏳',
            'accepted': '✅',
            'locked': '🔒',
            'trust_check': '🔍',
            'in_game_trade': '🎮',
            'verification': '📋',
            'completed': '✨',
            'disputed': '⚠️',
            'expired': '⏰',
            'cancelled': '❌'
        }
        
        status = trade.get('status', 'draft')
        embed.add_field(
            name="Status",
            value=f"{status_emoji.get(status, '❓')} {status.replace('_', ' ').title()}",
            inline=False
        )
        
        embed.set_footer(text=f"Trade ID: {trade.get('id', 'N/A')}")
        
        return embed
    
    @staticmethod
    def create_handoff(trade: Dict, game: str, platform: str = 'PC') -> discord.Embed:
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(
            title=f"🎮 In-Game Trade - {GAME_NAMES.get(game, game.upper())}",
            description="Please complete the trade in-game. Follow the instructions below.",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        instructions = {
            'ps99': {
                'PC': "1. Open Pet Simulator 99\n2. Join a trading plaza\n3. Find your trade partner\n4. Use the trade menu to complete the exchange",
                'Mobile': "1. Open Pet Simulator 99\n2. Tap the Trade button\n3. Join a plaza and find your partner\n4. Complete the trade through the menu"
            },
            'gag': {
                'PC': "1. Open Grow a Garden\n2. Go to the trading area\n3. Meet your trade partner\n4. Exchange items through the trade interface",
                'Mobile': "1. Open Grow a Garden\n2. Navigate to trading zone\n3. Find your partner and trade"
            },
            'am': {
                'PC': "1. Open Adopt Me\n2. Find your trade partner\n3. Click on them and select Trade\n4. Add your items and confirm",
                'Mobile': "1. Open Adopt Me\n2. Tap on your trade partner\n3. Select Trade option\n4. Add items and confirm"
            },
            'bf': {
                'PC': "1. Open Blox Fruits\n2. Go to a safe zone\n3. Use the trade function\n4. Complete the fruit/item exchange",
                'Mobile': "1. Open Blox Fruits\n2. Find a trading area\n3. Trade through the interface"
            },
            'sab': {
                'PC': "1. Open Steal a Brainrot\n2. Navigate to trading zone\n3. Complete the item exchange",
                'Mobile': "1. Open Steal a Brainrot\n2. Go to trade area\n3. Exchange items"
            }
        }
        
        game_instructions = instructions.get(game, {}).get(platform, "Follow the in-game trading instructions.")
        embed.add_field(name=f"📋 Instructions ({platform})", value=game_instructions, inline=False)
        
        embed.add_field(
            name="⚠️ Important",
            value="• Both parties must confirm the trade\n• Upload proof if requested\n• Report any issues immediately",
            inline=False
        )
        
        embed.set_footer(text=f"Trade ID: {trade.get('id', 'N/A')} | Complete within 15 minutes")
        
        return embed
    
    @staticmethod
    def create_receipt(trade: Dict, receipt_hash: str) -> discord.Embed:
        embed = discord.Embed(
            title="✨ Trade Receipt",
            description="This trade has been completed successfully.",
            color=0x2ECC71,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Trade ID", value=str(trade.get('id', 'N/A')), inline=True)
        embed.add_field(name="Game", value=GAME_NAMES.get(trade.get('game', ''), 'Unknown'), inline=True)
        embed.add_field(name="Completed", value=trade.get('completed_at', 'N/A'), inline=True)
        
        embed.add_field(
            name="🔐 Receipt Hash",
            value=f"`{receipt_hash[:32]}...`",
            inline=False
        )
        
        embed.set_footer(text="This receipt is immutable and can be verified with /verify_trade")
        
        return embed
    
    @staticmethod
    def create_risk_warning(risk_level: RiskLevel, warnings: List[str]) -> discord.Embed:
        color = RISK_COLORS.get(risk_level, 0xF39C12)
        
        title_map = {
            RiskLevel.SAFE: "✅ Trade Risk Assessment: Safe",
            RiskLevel.CAUTION: "⚠️ Trade Risk Assessment: Caution",
            RiskLevel.HIGH_RISK: "🚨 Trade Risk Assessment: High Risk"
        }
        
        embed = discord.Embed(
            title=title_map.get(risk_level, "Risk Assessment"),
            color=color
        )
        
        if warnings:
            embed.description = "\n".join([f"• {w}" for w in warnings])
        else:
            embed.description = "No significant risk factors detected."
        
        if risk_level == RiskLevel.HIGH_RISK:
            embed.add_field(
                name="⚠️ Required Actions",
                value="• Extra confirmation required\n• Proof may be mandatory\n• Moderators have been notified",
                inline=False
            )
        
        return embed


class ProfileEmbed:
    @staticmethod
    def create(user: discord.User, profile_data: Dict) -> discord.Embed:
        trust_score = profile_data.get('trust_score', 50)
        tier = profile_data.get('trust_tier', 'Bronze')
        tier_emoji = TIER_EMOJIS.get(tier, '🔰')
        
        if trust_score >= 90:
            color = 0xE91E63
        elif trust_score >= 75:
            color = 0x9C27B0
        elif trust_score >= 60:
            color = 0xFFD700
        elif trust_score >= 40:
            color = 0xC0C0C0
        else:
            color = 0xCD7F32
        
        embed = discord.Embed(
            title=f"{tier_emoji} {user.display_name}'s Trading Profile",
            color=color
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        
        embed.add_field(
            name="Trust Index",
            value=f"**{trust_score}/100**\nTier: {tier}",
            inline=True
        )
        
        total = profile_data.get('total_trades', 0)
        successful = profile_data.get('successful_trades', 0)
        ratio = (successful / total * 100) if total > 0 else 0
        
        embed.add_field(
            name="Trade Statistics",
            value=f"Total: {total}\nSuccessful: {successful}\nRatio: {ratio:.1f}%",
            inline=True
        )
        
        embed.add_field(
            name="Reputation Metrics",
            value=f"Reliability: {profile_data.get('reliability', 50):.0f}\n"
                  f"Fairness: {profile_data.get('fairness', 50):.0f}\n"
                  f"Responsiveness: {profile_data.get('responsiveness', 50):.0f}",
            inline=True
        )
        
        roblox_user = profile_data.get('roblox_username')
        if roblox_user:
            embed.add_field(name="Roblox Username", value=roblox_user, inline=True)
        
        disputed = profile_data.get('disputed_trades', 0)
        if disputed > 0:
            embed.add_field(name="⚠️ Disputes", value=str(disputed), inline=True)
        
        embed.set_footer(text=f"Member since {user.created_at.strftime('%Y-%m-%d')}")
        
        return embed


class InventoryEmbed:
    @staticmethod
    def create(user: discord.User, items: List[Dict], game: str, page: int = 1, total_pages: int = 1) -> discord.Embed:
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(
            title=f"📦 {user.display_name}'s Inventory - {GAME_NAMES.get(game, game.upper())}",
            color=color
        )
        
        if not items:
            embed.description = "No items in inventory for this game."
            return embed
        
        items_text = []
        for item in items[:10]:
            name = item.get('name', 'Unknown Item')
            rarity = item.get('rarity', '')
            quantity = item.get('quantity', 1)
            value = item.get('value', 0)
            
            rarity_emoji = {
                'Common': '⚪',
                'Uncommon': '🟢',
                'Rare': '🔵',
                'Epic': '🟣',
                'Legendary': '🟡',
                'Mythic': '🔴',
                'Titanic': '⭐',
                'Huge': '💫'
            }.get(rarity, '⚪')
            
            line = f"{rarity_emoji} **{name}**"
            if quantity > 1:
                line += f" x{quantity}"
            if value > 0:
                line += f" (Value: {value:,.0f})"
            items_text.append(line)
        
        embed.description = '\n'.join(items_text)
        embed.set_footer(text=f"Page {page}/{total_pages} | {len(items)} total items")
        
        return embed


class SearchEmbed:
    @staticmethod
    def create_results(query: str, items: List[Dict], game: str) -> discord.Embed:
        color = GAME_COLORS.get(game, 0x7289DA)
        
        embed = discord.Embed(
            title=f"🔍 Search Results - {GAME_NAMES.get(game, game.upper())}",
            description=f"Query: `{query}`",
            color=color
        )
        
        if not items:
            embed.add_field(name="No Results", value="No items found matching your query.", inline=False)
            return embed
        
        if items[0].get('icon_url'):
            embed.set_thumbnail(url=items[0]['icon_url'])
        
        rarity_emoji = {
            'Common': '⚪',
            'Uncommon': '🟢',
            'Rare': '🔵',
            'Epic': '🟣',
            'Legendary': '🟡',
            'Mythic': '🔴',
            'Titanic': '⭐',
            'Huge': '💫',
            'Ultra Rare': '💎',
            'Divine': '✨',
            'Secret': '🔮',
            'Mythical': '🌟'
        }
        
        for i, item in enumerate(items[:5], 1):
            name = item.get('name', 'Unknown')
            rarity = item.get('rarity', 'Unknown')
            value = item.get('value', 0)
            
            emoji = rarity_emoji.get(rarity, '⚪')
            
            if value >= 1_000_000_000_000:
                value_str = f"{value / 1_000_000_000_000:.1f}T"
            elif value >= 1_000_000_000:
                value_str = f"{value / 1_000_000_000:.1f}B"
            elif value >= 1_000_000:
                value_str = f"{value / 1_000_000:.1f}M"
            elif value >= 1_000:
                value_str = f"{value / 1_000:.1f}K"
            else:
                value_str = f"{value:,.0f}"
            
            field_value = f"{emoji} {rarity}\n💰 {value_str}"
            embed.add_field(name=f"{i}. {name}", value=field_value, inline=True)
        
        if len(items) > 5:
            embed.set_footer(text=f"Showing 5 of {len(items)} results | Use /item for more details")
        else:
            embed.set_footer(text="Use /item for more details on a specific item")
        
        return embed
