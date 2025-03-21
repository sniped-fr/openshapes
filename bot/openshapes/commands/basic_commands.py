import discord
import logging
from typing import Dict, List, Any

logger = logging.getLogger("openshape")

class PaginationView(discord.ui.View):
    def __init__(self, embeds: List[discord.Embed]):
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

class CharacterField:
    def __init__(self, name: str, value: str, inline: bool = False):
        self.name = name
        self.value = value[:1024]
        self.inline = inline
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "inline": self.inline
        }
        
    @property
    def size(self) -> int:
        return len(self.name) + len(self.value)

class CharacterInfoBuilder:
    def __init__(self, bot: Any):
        self.bot = bot
        self.embed_color = 0x3498DB
        
    def create_fields(self) -> List[CharacterField]:
        fields = []
        
        if self.bot.character_backstory:
            fields.append(CharacterField("Backstory", self.bot.character_backstory, False))
        
        if self.bot.character_description:
            fields.append(CharacterField("Appearance", self.bot.character_description, False))
        
        if self.bot.character_scenario:
            fields.append(CharacterField("Scenario", self.bot.character_scenario, False))
        
        if self.bot.personality_age:
            fields.append(CharacterField("Age", self.bot.personality_age, True))
        
        if self.bot.personality_traits:
            fields.append(CharacterField("Traits", self.bot.personality_traits, True))
        
        if self.bot.personality_likes:
            fields.append(CharacterField("Likes", self.bot.personality_likes, True))
        
        if self.bot.personality_dislikes:
            fields.append(CharacterField("Dislikes", self.bot.personality_dislikes, True))
        
        if self.bot.personality_tone:
            fields.append(CharacterField("Tone", self.bot.personality_tone, True))
        
        if self.bot.jailbreak:
            fields.append(CharacterField("Presets", self.bot.jailbreak, True))
        
        if self.bot.personality_history:
            fields.append(CharacterField("History", self.bot.personality_history, False))
            
        return fields
        
    def build_embeds(self) -> List[discord.Embed]:
        fields = self.create_fields()
        embeds = []
        
        embed = discord.Embed(title=f"{self.bot.character_name} Info", color=self.embed_color)
        current_size = len(embed.title)
        
        for field in fields:
            field_dict = field.to_dict()
            
            if current_size + field.size > 5800:
                embeds.append(embed)
                embed = discord.Embed(title=f"{self.bot.character_name} Info (Continued)", color=self.embed_color)
                current_size = len(embed.title)
            
            embed.add_field(
                name=field_dict["name"],
                value=field_dict["value"],
                inline=field_dict["inline"]
            )
            current_size += field.size
        
        embeds.append(embed)
        return embeds

class ChannelActivationManager:
    def __init__(self, bot: Any):
        self.bot = bot
        
    def activate_channel(self, channel_id: int) -> None:
        self.bot.activated_channels.add(channel_id)
        self.bot.config_manager_obj.save_config()
        
    def deactivate_channel(self, channel_id: int) -> None:
        if channel_id in self.bot.activated_channels:
            self.bot.activated_channels.remove(channel_id)
            self.bot.config_manager_obj.save_config()

class BasicCommandsHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        self.info_builder = CharacterInfoBuilder(bot)
        self.activation_manager = ChannelActivationManager(bot)
        
    async def handle_character_info(self, interaction: discord.Interaction) -> None:
        embeds = self.info_builder.build_embeds()
        
        if len(embeds) == 1:
            await interaction.response.send_message(embed=embeds[0])
        else:
            view = PaginationView(embeds)
            await interaction.response.send_message(embed=embeds[0], view=view)
            
    async def handle_activate(self, interaction: discord.Interaction) -> None:
        self.activation_manager.activate_channel(interaction.channel_id)
        await interaction.response.send_message(
            f"{self.bot.character_name} will now respond to all messages in this channel."
        )
        
    async def handle_deactivate(self, interaction: discord.Interaction) -> None:
        self.activation_manager.deactivate_channel(interaction.channel_id)
        await interaction.response.send_message(
            f"{self.bot.character_name} will now only respond when mentioned or called by name."
        )
        
    async def handle_models(self, interaction: discord.Interaction) -> None:
        from openshapes.models.model_selector import model_command
        await model_command(self.bot, interaction)

async def character_info_command(self, interaction: discord.Interaction) -> None:
    handler = BasicCommandsHandler(self)
    await handler.handle_character_info(interaction)

async def activate_command(self, interaction: discord.Interaction) -> None:
    handler = BasicCommandsHandler(self)
    await handler.handle_activate(interaction)

async def deactivate_command(self, interaction: discord.Interaction) -> None:
    handler = BasicCommandsHandler(self)
    await handler.handle_deactivate(interaction)
    
async def models_command(self, interaction: discord.Interaction) -> None:
    handler = BasicCommandsHandler(self)
    await handler.handle_models(interaction)
