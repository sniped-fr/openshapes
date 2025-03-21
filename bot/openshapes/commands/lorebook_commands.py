import discord
import logging
from openshapes.utils.views import LorebookManagementView

logger = logging.getLogger("openshape")

async def lorebook_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        if not self.lorebook_entries:
            await interaction.response.send_message(
                "No lorebook entries exist yet."
            )
            return

        lore_embeds = []
        for entry in self.lorebook_entries:
            embed = discord.Embed(
                title=f"Lorebook: {entry['keyword']}",
                description=entry["content"],
                color=0x9B59B6,
            )
            lore_embeds.append(embed)

        await interaction.response.send_message(embeds=lore_embeds)
        return

    view = LorebookManagementView(self)
    lore_display = self.lorebook_manager.format_entries_for_display()
    await interaction.response.send_message(lore_display, view=view)
