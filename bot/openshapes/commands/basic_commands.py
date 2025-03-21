import discord
import logging

logger = logging.getLogger("openshape")

async def character_info_command(self, interaction: discord.Interaction):
    class PaginationView(discord.ui.View):
        def __init__(self, embeds):
            super().__init__(timeout=120)
            self.embeds = embeds
            self.current_page = 0
            self.total_pages = len(embeds)
            for i, embed in enumerate(self.embeds):
                embed.set_footer(text=f"Page {i+1}/{self.total_pages}")
        
        @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary, disabled=True)
        async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = max(0, self.current_page - 1)
            self.previous_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page == self.total_pages - 1
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

        @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = min(self.total_pages - 1, self.current_page + 1)
            self.previous_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page == self.total_pages - 1
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
            
    embeds = []
    
    embed = discord.Embed(title=f"{self.character_name} Info", color=0x3498DB)
    current_size = len(embed.title)
    
    fields = []
    
    if self.character_backstory:
        fields.append({
            "name": "Backstory",
            "value": self.character_backstory[:1024],
            "inline": False
        })
    
    if self.character_description:
        fields.append({
            "name": "Appearance",
            "value": self.character_description[:1024],
            "inline": False
        })
    
    if self.character_scenario:
        fields.append({
            "name": "Scenario",
            "value": self.character_scenario[:1024],
            "inline": False
        })
    
    if self.personality_age:
        fields.append({
            "name": "Age",
            "value": self.personality_age[:1024],
            "inline": True
        })
    
    if self.personality_traits:
        fields.append({
            "name": "Traits",
            "value": self.personality_traits[:1024],
            "inline": True
        })
    
    if self.personality_likes:
        fields.append({
            "name": "Likes",
            "value": self.personality_likes[:1024],
            "inline": True
        })
    
    if self.personality_dislikes:
        fields.append({
            "name": "Dislikes",
            "value": self.personality_dislikes[:1024],
            "inline": True
        })
    
    if self.personality_tone:
        fields.append({
            "name": "Tone",
            "value": self.personality_tone[:1024],
            "inline": True
        })
    
    if self.jailbreak:
        fields.append({
            "name": "Presets",
            "value": self.jailbreak[:1024],
            "inline": True
        })
    
    if self.personality_history:
        fields.append({
            "name": "History",
            "value": self.personality_history[:1024],
            "inline": False
        })
    
    for field in fields:
        field_size = len(field["name"]) + len(field["value"])
        
        if current_size + field_size > 5800:
            embeds.append(embed)
            embed = discord.Embed(title=f"{self.character_name} Info (Continued)", color=0x3498DB)
            current_size = len(embed.title)
        
        embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])
        current_size += field_size
    
    embeds.append(embed)
    
    if len(embeds) == 1:
        await interaction.response.send_message(embed=embeds[0])
    else:
        view = PaginationView(embeds)
        await interaction.response.send_message(embed=embeds[0], view=view)

async def activate_command(self, interaction: discord.Interaction):
    self.activated_channels.add(interaction.channel_id)
    self.config_manager.save_config()
    await interaction.response.send_message(
        f"{self.character_name} will now respond to all messages in this channel."
    )

async def deactivate_command(self, interaction: discord.Interaction):
    if interaction.channel_id in self.activated_channels:
        self.activated_channels.remove(interaction.channel_id)
        self.config_manager.save_config()
    await interaction.response.send_message(
        f"{self.character_name} will now only respond when mentioned or called by name."
    )
    
async def models_command(self, interaction: discord.Interaction):
    from openshapes.models.model_selector import model_command
    await model_command(self, interaction)
