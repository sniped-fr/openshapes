import discord
import logging
from typing import Any, List, Dict
from openshapes.utils.views import LorebookManagementView

logger = logging.getLogger("openshape")

class LorebookEmbedBuilder:
    @staticmethod
    def build_lore_embeds(entries: List[Dict[str, str]]) -> List[discord.Embed]:
        lore_embeds = []
        for entry in entries:
            embed = discord.Embed(
                title=f"Lorebook: {entry['keyword']}",
                description=entry["content"],
                color=0x9B59B6,
            )
            lore_embeds.append(embed)
        return lore_embeds

class LorebookCommandHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def handle_regular_user_view(self, interaction: discord.Interaction) -> None:
        if not self.bot.lorebook_entries:
            await interaction.response.send_message("No lorebook entries exist yet.")
            return

        lore_embeds = LorebookEmbedBuilder.build_lore_embeds(self.bot.lorebook_entries)
        await interaction.response.send_message(embeds=lore_embeds)
        
    async def handle_owner_view(self, interaction: discord.Interaction) -> None:
        view = LorebookManagementView(self.bot)
        lore_display = self.bot.lorebook_manager.format_entries_for_display()
        await interaction.response.send_message(lore_display, view=view)
        
    async def handle_lorebook_command(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.bot.owner_id:
            await self.handle_regular_user_view(interaction)
        else:
            await self.handle_owner_view(interaction)

async def lorebook_command(self, interaction: discord.Interaction) -> None:
    handler = LorebookCommandHandler(self)
    await handler.handle_lorebook_command(interaction)
