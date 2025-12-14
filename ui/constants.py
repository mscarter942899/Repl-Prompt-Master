import discord

DIAMONDS_EMOJI = "<:diamonds:1449866490495893577>"

GAME_EMOJIS = {
    'ps99': '🐾',
    'gag': '🌱',
    'am': '🏠',
    'bf': '🍎',
    'sab': '🧠'
}

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

RARITY_EMOJIS = {
    'Common': '⚪',
    'Uncommon': '🟢',
    'Rare': '🔵',
    'Epic': '🟣',
    'Legendary': '🟡',
    'Mythic': '🔴',
    'Titanic': '⭐',
    'Huge': '💫',
    'Divine': '✨',
    'Secret': '🔮',
    'Mythical': '🌟',
    'Ultra Rare': '💠',
    'Exclusive': '🎭',
    'Event': '🎃',
    'Limited': '🏆'
}

TIER_EMOJIS = {
    'Bronze': '🥉',
    'Silver': '🥈',
    'Gold': '🥇',
    'Platinum': '💎',
    'Diamond': '👑'
}

TRADE_STATUS_EMOJIS = {
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


def format_value(value: float) -> str:
    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.2f}K"
    else:
        return f"{value:,.0f}"


def format_gems(amount: int) -> str:
    return f"{DIAMONDS_EMOJI} **{format_value(amount)}**"
