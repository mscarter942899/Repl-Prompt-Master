import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
import json
import logging

from utils.database import (
    upsert_item, get_item, search_items as db_search_items, delete_item, 
    get_all_items_for_game, update_item_field, init_database
)

logger = logging.getLogger('ItemManage')

ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
MAX_IMAGE_SIZE = 8 * 1024 * 1024  # 8MB

GAME_CHOICES = [
    app_commands.Choice(name="Pet Simulator 99", value="ps99"),
    app_commands.Choice(name="Grow a Garden", value="gag"),
    app_commands.Choice(name="Adopt Me", value="am"),
    app_commands.Choice(name="Blox Fruits", value="bf"),
    app_commands.Choice(name="Steal a Brainrot", value="sab")
]

GAME_NAMES = {
    'ps99': 'Pet Simulator 99',
    'gag': 'Grow a Garden',
    'am': 'Adopt Me',
    'bf': 'Blox Fruits',
    'sab': 'Steal a Brainrot'
}

RARITY_CHOICES = [
    app_commands.Choice(name="Common", value="Common"),
    app_commands.Choice(name="Uncommon", value="Uncommon"),
    app_commands.Choice(name="Rare", value="Rare"),
    app_commands.Choice(name="Epic", value="Epic"),
    app_commands.Choice(name="Legendary", value="Legendary"),
    app_commands.Choice(name="Mythical", value="Mythical"),
    app_commands.Choice(name="Secret", value="Secret"),
    app_commands.Choice(name="Exclusive", value="Exclusive"),
    app_commands.Choice(name="Limited", value="Limited"),
    app_commands.Choice(name="Event", value="Event")
]


def is_owner_or_admin():
    """Check if user is bot owner OR has administrator permission in the server."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if hasattr(interaction.client, 'is_owner'):
            if await interaction.client.is_owner(interaction.user):
                return True
        
        if interaction.guild and isinstance(interaction.user, discord.Member):
            if interaction.user.guild_permissions.administrator:
                return True
        
        await interaction.response.send_message(
            "You need Administrator permission to use this command.",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)


async def process_image_upload(attachment: discord.Attachment, interaction: discord.Interaction) -> Optional[str]:
    """
    Process an uploaded image attachment and return a permanent URL.
    Uses the original attachment URL which Discord keeps accessible.
    """
    if attachment.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Invalid image type. Allowed: PNG, JPEG, GIF, WebP")
    
    if attachment.size > MAX_IMAGE_SIZE:
        raise ValueError(f"Image too large. Maximum size: 8MB")
    
    try:
        return attachment.url
        
    except Exception as e:
        logger.error(f"Error processing image upload: {e}")
        raise ValueError(f"Failed to process image: {str(e)}")


class ItemManageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    item_group = app_commands.Group(name="manage", description="Manage items in the database")

    async def item_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        game = None
        if interaction.data:
            options = interaction.data.get('options', [])
            if options:
                for opt in options:
                    if isinstance(opt, dict):
                        if opt.get('name') == 'game':
                            game = str(opt.get('value', ''))
                        elif opt.get('type') == 1:
                            sub_options = opt.get('options', [])
                            for sub_opt in sub_options:
                                if isinstance(sub_opt, dict) and sub_opt.get('name') == 'game':
                                    game = str(sub_opt.get('value', ''))
                                    break

        if not game:
            return []

        try:
            if not current:
                items = await get_all_items_for_game(game, limit=25)
            else:
                items = await db_search_items(game, current, limit=25)
            
            return [
                app_commands.Choice(
                    name=f"{item['name'][:50]} ({item.get('value', 0):,.0f})"[:100], 
                    value=item['item_id'][:100]
                )
                for item in items
            ]
        except Exception:
            return []

    @item_group.command(name="add", description="Add a new item to the database")
    @is_owner_or_admin()
    @app_commands.describe(
        game="The game this item belongs to",
        item_id="Unique identifier for the item",
        name="Display name of the item",
        value="The item's value/worth",
        rarity="The item's rarity tier",
        image="Upload an image from your device (optional)",
        image_url="URL to the item's image (optional, use if not uploading)",
        tradeable="Whether this item can be traded"
    )
    @app_commands.choices(game=GAME_CHOICES, rarity=RARITY_CHOICES)
    async def add_item(
        self, 
        interaction: discord.Interaction, 
        game: str,
        item_id: str,
        name: str,
        value: float,
        rarity: Optional[str] = "Common",
        image: Optional[discord.Attachment] = None,
        image_url: Optional[str] = None,
        tradeable: Optional[bool] = True
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            existing = await get_item(game, item_id)
            if existing:
                await interaction.followup.send(
                    f"An item with ID `{item_id}` already exists in {GAME_NAMES.get(game, game)}.\n"
                    f"Use `/manage update` to modify it.",
                    ephemeral=True
                )
                return

            final_image_url = None
            if image:
                try:
                    final_image_url = await process_image_upload(image, interaction)
                except ValueError as e:
                    await interaction.followup.send(f"Image error: {str(e)}", ephemeral=True)
                    return
            elif image_url:
                final_image_url = image_url

            await upsert_item(
                game=game,
                item_id=item_id,
                name=name,
                value=value,
                rarity=rarity,
                icon_url=final_image_url,
                tradeable=1 if tradeable else 0,
                source='manual'
            )

            embed = discord.Embed(
                title="Item Added",
                description=f"Successfully added **{name}** to {GAME_NAMES.get(game, game)}",
                color=0x2ECC71
            )
            embed.add_field(name="Item ID", value=item_id, inline=True)
            embed.add_field(name="Value", value=f"{value:,.0f}", inline=True)
            embed.add_field(name="Rarity", value=rarity, inline=True)
            embed.add_field(name="Tradeable", value="Yes" if tradeable else "No", inline=True)
            
            if final_image_url:
                embed.set_thumbnail(url=final_image_url)
                embed.add_field(name="Image", value="✅ Uploaded" if image else "✅ URL Set", inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error adding item: {str(e)}", ephemeral=True)

    @item_group.command(name="update", description="Update an existing item's details")
    @is_owner_or_admin()
    @app_commands.describe(
        game="The game this item belongs to",
        item_id="The item to update",
        name="New display name (leave empty to keep current)",
        value="New value (leave empty to keep current)",
        rarity="New rarity (leave empty to keep current)",
        image="Upload a new image from your device (optional)",
        image_url="New image URL (leave empty to keep current)",
        tradeable="Whether this item can be traded"
    )
    @app_commands.choices(game=GAME_CHOICES, rarity=RARITY_CHOICES)
    @app_commands.autocomplete(item_id=item_autocomplete)
    async def update_item(
        self,
        interaction: discord.Interaction,
        game: str,
        item_id: str,
        name: Optional[str] = None,
        value: Optional[float] = None,
        rarity: Optional[str] = None,
        image: Optional[discord.Attachment] = None,
        image_url: Optional[str] = None,
        tradeable: Optional[bool] = None
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            existing = await get_item(game, item_id)
            if not existing:
                await interaction.followup.send(
                    f"Item `{item_id}` not found in {GAME_NAMES.get(game, game)}.",
                    ephemeral=True
                )
                return

            updates = {}
            image_uploaded = False
            if name is not None:
                updates['name'] = name
            if value is not None:
                updates['value'] = value
            if rarity is not None:
                updates['rarity'] = rarity
            if image:
                try:
                    uploaded_url = await process_image_upload(image, interaction)
                    if uploaded_url:
                        updates['icon_url'] = uploaded_url
                        image_uploaded = True
                except ValueError as e:
                    await interaction.followup.send(f"Image error: {str(e)}", ephemeral=True)
                    return
            elif image_url is not None:
                updates['icon_url'] = image_url
            if tradeable is not None:
                updates['tradeable'] = 1 if tradeable else 0

            if not updates:
                await interaction.followup.send("No updates provided.", ephemeral=True)
                return

            for field, val in updates.items():
                await update_item_field(game, item_id, field, val)

            embed = discord.Embed(
                title="Item Updated",
                description=f"Updated **{existing['name']}** in {GAME_NAMES.get(game, game)}",
                color=0x3498DB
            )
            
            for field, val in updates.items():
                display_name = field.replace('_', ' ').title()
                if field == 'icon_url':
                    display_name = 'Image'
                    val = '📤 Uploaded' if image_uploaded else '🔗 URL Updated'
                elif field == 'tradeable':
                    val = 'Yes' if val else 'No'
                elif isinstance(val, float):
                    val = f"{val:,.0f}"
                embed.add_field(name=display_name, value=str(val), inline=True)

            updated_item = await get_item(game, item_id)
            if updated_item and updated_item.get('icon_url'):
                embed.set_thumbnail(url=updated_item['icon_url'])

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error updating item: {str(e)}", ephemeral=True)

    @item_group.command(name="setimage", description="Set or update an item's image")
    @is_owner_or_admin()
    @app_commands.describe(
        game="The game this item belongs to",
        item_id="The item to update",
        image="Upload an image from your device",
        image_url="URL to the item's image (use if not uploading)"
    )
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.autocomplete(item_id=item_autocomplete)
    async def set_image(
        self,
        interaction: discord.Interaction,
        game: str,
        item_id: str,
        image: Optional[discord.Attachment] = None,
        image_url: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            if not image and not image_url:
                await interaction.followup.send(
                    "Please provide either an image upload or an image URL.",
                    ephemeral=True
                )
                return

            existing = await get_item(game, item_id)
            if not existing:
                await interaction.followup.send(
                    f"Item `{item_id}` not found in {GAME_NAMES.get(game, game)}.",
                    ephemeral=True
                )
                return

            final_image_url = None
            if image:
                try:
                    final_image_url = await process_image_upload(image, interaction)
                except ValueError as e:
                    await interaction.followup.send(f"Image error: {str(e)}", ephemeral=True)
                    return
            elif image_url:
                final_image_url = image_url

            if final_image_url:
                await update_item_field(game, item_id, 'icon_url', final_image_url)

            embed = discord.Embed(
                title="Image Updated",
                description=f"Set image for **{existing['name']}**",
                color=0x9B59B6
            )
            if final_image_url:
                embed.set_thumbnail(url=final_image_url)
            embed.add_field(name="Game", value=GAME_NAMES.get(game, game), inline=True)
            embed.add_field(name="Item ID", value=item_id, inline=True)
            embed.add_field(name="Source", value="📤 Uploaded" if image else "🔗 URL", inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error setting image: {str(e)}", ephemeral=True)

    @item_group.command(name="setvalue", description="Quickly set an item's value")
    @is_owner_or_admin()
    @app_commands.describe(
        game="The game this item belongs to",
        item_id="The item to update",
        value="The new value"
    )
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.autocomplete(item_id=item_autocomplete)
    async def set_value(
        self,
        interaction: discord.Interaction,
        game: str,
        item_id: str,
        value: float
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            existing = await get_item(game, item_id)
            if not existing:
                await interaction.followup.send(
                    f"Item `{item_id}` not found in {GAME_NAMES.get(game, game)}.",
                    ephemeral=True
                )
                return

            old_value = existing.get('value', 0)
            await update_item_field(game, item_id, 'value', value)

            embed = discord.Embed(
                title="Value Updated",
                description=f"Updated value for **{existing['name']}**",
                color=0xF1C40F
            )
            embed.add_field(name="Old Value", value=f"{old_value:,.0f}", inline=True)
            embed.add_field(name="New Value", value=f"{value:,.0f}", inline=True)
            
            change = value - old_value
            if change > 0:
                embed.add_field(name="Change", value=f"+{change:,.0f}", inline=True)
            else:
                embed.add_field(name="Change", value=f"{change:,.0f}", inline=True)

            if existing.get('icon_url'):
                embed.set_thumbnail(url=existing['icon_url'])

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error setting value: {str(e)}", ephemeral=True)

    @item_group.command(name="delete", description="Delete an item from the database")
    @is_owner_or_admin()
    @app_commands.describe(
        game="The game this item belongs to",
        item_id="The item to delete"
    )
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.autocomplete(item_id=item_autocomplete)
    async def delete_item_cmd(
        self,
        interaction: discord.Interaction,
        game: str,
        item_id: str
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            existing = await get_item(game, item_id)
            if not existing:
                await interaction.followup.send(
                    f"Item `{item_id}` not found in {GAME_NAMES.get(game, game)}.",
                    ephemeral=True
                )
                return

            await delete_item(game, item_id)

            embed = discord.Embed(
                title="Item Deleted",
                description=f"Removed **{existing['name']}** from {GAME_NAMES.get(game, game)}",
                color=0xE74C3C
            )
            embed.add_field(name="Item ID", value=item_id, inline=True)
            embed.add_field(name="Value", value=f"{existing.get('value', 0):,.0f}", inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error deleting item: {str(e)}", ephemeral=True)

    @item_group.command(name="list", description="List all items for a game")
    @is_owner_or_admin()
    @app_commands.describe(
        game="The game to list items for",
        page="Page number (25 items per page)"
    )
    @app_commands.choices(game=GAME_CHOICES)
    async def list_items(
        self,
        interaction: discord.Interaction,
        game: str,
        page: Optional[int] = 1
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            all_items = await get_all_items_for_game(game, limit=1000)
            
            if not all_items:
                await interaction.followup.send(
                    f"No items found in {GAME_NAMES.get(game, game)}.\n"
                    f"Use `/manage add` to add items.",
                    ephemeral=True
                )
                return

            items_per_page = 25
            total_pages = (len(all_items) + items_per_page - 1) // items_per_page
            current_page = max(1, min(page or 1, total_pages))
            
            start_idx = (current_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_items = all_items[start_idx:end_idx]

            embed = discord.Embed(
                title=f"Items - {GAME_NAMES.get(game, game)}",
                description=f"Page {current_page}/{total_pages} | Total: {len(all_items)} items",
                color=0x3498DB
            )

            item_list = []
            for item in page_items:
                name = item['name'][:30]
                value = item.get('value', 0)
                rarity = item.get('rarity', 'Unknown')[:10]
                has_image = "🖼️" if item.get('icon_url') else ""
                item_list.append(f"**{name}** {has_image}\n`{value:,.0f}` | {rarity}")

            chunks = [item_list[i:i+5] for i in range(0, len(item_list), 5)]
            for i, chunk in enumerate(chunks[:5]):
                embed.add_field(
                    name=f"Items {start_idx + i*5 + 1}-{start_idx + min((i+1)*5, len(page_items))}",
                    value="\n".join(chunk),
                    inline=True
                )

            embed.set_footer(text=f"Use /manage list game:{game} page:{current_page+1} for more")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error listing items: {str(e)}", ephemeral=True)

    @item_group.command(name="bulkvalue", description="Update values for multiple items")
    @is_owner_or_admin()
    @app_commands.describe(
        game="The game these items belong to",
        updates="JSON format: {\"item_id\": value, \"item_id2\": value2}"
    )
    @app_commands.choices(game=GAME_CHOICES)
    async def bulk_value(
        self,
        interaction: discord.Interaction,
        game: str,
        updates: str
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            update_dict = json.loads(updates)
        except json.JSONDecodeError:
            await interaction.followup.send(
                "Invalid JSON format. Use: `{\"item_id\": 1000, \"item_id2\": 2000}`",
                ephemeral=True
            )
            return

        success = []
        failed = []

        for item_id, value in update_dict.items():
            try:
                existing = await get_item(game, item_id)
                if existing:
                    await update_item_field(game, item_id, 'value', float(value))
                    success.append(f"✅ {existing['name']}: {value:,.0f}")
                else:
                    failed.append(f"❌ {item_id}: Not found")
            except Exception as e:
                failed.append(f"❌ {item_id}: {str(e)[:30]}")

        embed = discord.Embed(
            title="Bulk Value Update",
            color=0x2ECC71 if not failed else 0xF39C12
        )
        
        if success:
            embed.add_field(
                name=f"Updated ({len(success)})",
                value="\n".join(success[:10]) + (f"\n...and {len(success)-10} more" if len(success) > 10 else ""),
                inline=False
            )
        
        if failed:
            embed.add_field(
                name=f"Failed ({len(failed)})",
                value="\n".join(failed[:10]),
                inline=False
            )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ItemManageCog(bot))
