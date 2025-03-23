import logging
import discord
from typing import Dict, List, Callable, Awaitable, TypeVar, cast
from discord.ext import commands
from openshapes.views import TextEditModal

logger = logging.getLogger("openshape")

T = TypeVar('T')
ModalSubmitCallback = Callable[[discord.Interaction], Awaitable[None]]

class PermissionChecker:
    @staticmethod
    async def check_owner_permission(interaction: discord.Interaction, owner_id: int) -> bool:
        if interaction.user.id != owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return False
        return True

class SelectOptionBuilder:
    @staticmethod
    def build_personality_trait_options() -> List[discord.SelectOption]:
        return [
            discord.SelectOption(label="Catchphrases", value="catchphrases"),
            discord.SelectOption(label="Age", value="age"),
            discord.SelectOption(label="Traits", value="traits"),
            discord.SelectOption(label="Physical Traits", value="physical"),
            discord.SelectOption(label="Tone", value="tone"),
            discord.SelectOption(label="Conversational Style", value="style"),
        ]
        
    @staticmethod
    def build_preference_options() -> List[discord.SelectOption]:
        return [
            discord.SelectOption(label="Likes", value="likes"),
            discord.SelectOption(label="Dislikes", value="dislikes"),
            discord.SelectOption(label="Goals", value="goals"),
        ]

class SelectMenuBuilder:
    @staticmethod
    def build_select_menu(
        options: List[discord.SelectOption],
        placeholder: str,
        callback: Callable[[discord.Interaction], Awaitable[None]]
    ) -> discord.ui.Select:
        select = discord.ui.Select(placeholder=placeholder, options=options)
        select.callback = callback
        return select
        
    @staticmethod
    def build_view_with_select(select: discord.ui.Select) -> discord.ui.View:
        view = discord.ui.View()
        view.add_item(select)
        return view

class PersonalityEditor:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    def get_trait_values(self) -> Dict[str, str]:
        return {
            "catchphrases": self.bot.personality_catchphrases or "",
            "age": self.bot.personality_age or "",
            "traits": self.bot.personality_traits or "",
            "physical": self.bot.personality_physical_traits or "",
            "tone": self.bot.personality_tone or "",
            "style": self.bot.personality_conversational_examples or ""
        }
        
    def get_preference_values(self) -> Dict[str, str]:
        return {
            "likes": self.bot.personality_likes or "",
            "dislikes": self.bot.personality_dislikes or "",
            "goals": self.bot.personality_goals or ""
        }
        
    def update_trait(self, trait: str, value: str) -> None:
        if trait == "catchphrases":
            self.bot.personality_catchphrases = value
        elif trait == "age":
            self.bot.personality_age = value
        elif trait == "traits":
            self.bot.personality_traits = value
        elif trait == "physical":
            self.bot.personality_physical_traits = value
        elif trait == "tone":
            self.bot.personality_tone = value
        elif trait == "style":
            self.bot.personality_conversational_examples = value
            
        self.bot.config_manager_obj.save_config()
        
    def update_preference(self, preference: str, value: str) -> None:
        if preference == "likes":
            self.bot.personality_likes = value
        elif preference == "dislikes":
            self.bot.personality_dislikes = value
        elif preference == "goals":
            self.bot.personality_goals = value
            
        self.bot.config_manager_obj.save_config()
        
    def update_backstory(self, value: str) -> None:
        self.bot.personality_history = value
        self.bot.config_manager_obj.save_config()
        
    async def create_trait_modal(self, trait: str, interaction: discord.Interaction) -> None:
        values = self.get_trait_values()
        modal = TextEditModal(
            title=f"Edit {trait.title()}",
            current_text=values[trait]
        )

        async def on_submit(modal_interaction: discord.Interaction) -> None:
            self.update_trait(trait, modal.text_input.value)
            await modal_interaction.response.send_message(
                f"Character {trait} updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def create_preference_modal(self, preference: str, interaction: discord.Interaction) -> None:
        values = self.get_preference_values()
        modal = TextEditModal(
            title=f"Edit {preference.title()}",
            current_text=values[preference]
        )

        async def on_submit(modal_interaction: discord.Interaction) -> None:
            self.update_preference(preference, modal.text_input.value)
            await modal_interaction.response.send_message(
                f"Character {preference} updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

class PersonalityCommandHandler:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.editor = PersonalityEditor(bot)
        
    async def handle_personality_traits_edit(self, interaction: discord.Interaction) -> None:
        if not await PermissionChecker.check_owner_permission(interaction, self.bot.config_manager.get("owner_id")):
            return

        options = SelectOptionBuilder.build_personality_trait_options()

        async def select_callback(select_interaction: discord.Interaction) -> None:
            trait = cast(discord.ui.Select, select_interaction.data["components"][0]["components"][0])
            trait_value = trait["values"][0]
            await self.editor.create_trait_modal(trait_value, select_interaction)

        select = SelectMenuBuilder.build_select_menu(
            options,
            "Select trait to edit",
            select_callback
        )
        view = SelectMenuBuilder.build_view_with_select(select)

        await interaction.response.send_message(
            "Select a personality trait to edit:", view=view, ephemeral=True
        )
        
    async def handle_backstory_edit(self, interaction: discord.Interaction) -> None:
        if not await PermissionChecker.check_owner_permission(interaction, self.bot.config_manager.get("owner_id")):
            return

        modal = TextEditModal(
            title="Edit Character History",
            current_text=self.bot.personality_history or ""
        )

        async def on_submit(modal_interaction: discord.Interaction) -> None:
            self.editor.update_backstory(modal.text_input.value)
            await modal_interaction.response.send_message(
                "Character history updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def handle_preferences_edit(self, interaction: discord.Interaction) -> None:
        if not await PermissionChecker.check_owner_permission(interaction, self.bot.config_manager.get("owner_id")):
            return

        options = SelectOptionBuilder.build_preference_options()

        async def select_callback(select_interaction: discord.Interaction) -> None:
            preference = cast(discord.ui.Select, select_interaction.data["components"][0]["components"][0])
            await self.editor.create_preference_modal(preference["values"][0], select_interaction)

        select = SelectMenuBuilder.build_select_menu(
            options,
            "Select preference to edit",
            select_callback
        )
        view = SelectMenuBuilder.build_view_with_select(select)

        await interaction.response.send_message(
            "Select preferences to edit:", view=view, ephemeral=True
        )

class PersonalityCommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="edit_personality_traits", description="Edit character personality traits")
    async def edit_personality_traits(self, interaction: discord.Interaction) -> None:
        handler = PersonalityCommandHandler(self.bot)
        await handler.handle_personality_traits_edit(interaction)

    @discord.app_commands.command(name="edit_backstory", description="Edit character backstory")
    async def edit_backstory(self, interaction: discord.Interaction) -> None:
        handler = PersonalityCommandHandler(self.bot)
        await handler.handle_backstory_edit(interaction)

    @discord.app_commands.command(name="edit_preferences", description="Edit character preferences")
    async def edit_preferences(self, interaction: discord.Interaction) -> None:
        handler = PersonalityCommandHandler(self.bot)
        await handler.handle_preferences_edit(interaction)

async def setup(bot: commands.Bot):
    await bot.add_cog(PersonalityCommandsCog(bot))
