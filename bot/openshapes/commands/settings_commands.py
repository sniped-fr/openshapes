import discord
import logging
from typing import Any, List
from openshapes.utils.views import TextEditModal, UserIDModal, SettingsView, RegexManagementView

logger = logging.getLogger("openshape")

class SettingsFormatter:
    @staticmethod
    def format_settings(bot: Any) -> str:
        settings_display = f"**{bot.character_name} Settings:**\n"
        settings_display += f"- Add name to responses: {'Enabled' if bot.add_character_name else 'Disabled'}\n"
        settings_display += f"- Reply to mentions: {'Enabled' if bot.always_reply_mentions else 'Disabled'}\n"
        settings_display += f"- Reply when name is called: {'Enabled' if bot.reply_to_name else 'Disabled'}\n"
        return settings_display

class PermissionValidator:
    @staticmethod
    async def validate_owner(interaction: discord.Interaction, owner_id: int) -> bool:
        if interaction.user.id != owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return False
        return True

class BlacklistOption:
    VIEW = "view"
    ADD_USER = "add_user"
    REMOVE_USER = "remove_user"

class CharacterEditor:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def edit_prompt(self, interaction: discord.Interaction) -> None:
        if not await PermissionValidator.validate_owner(interaction, self.bot.owner_id):
            return
            
        modal = TextEditModal(
            title="Edit System Prompt",
            current_text=self.bot.system_prompt
        )

        async def on_submit(modal_interaction: discord.Interaction) -> None:
            self.bot.system_prompt = modal.text_input.value
            self.bot.config_manager_obj.save_config()
            await modal_interaction.response.send_message(
                "System prompt updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def edit_description(self, interaction: discord.Interaction) -> None:
        if not await PermissionValidator.validate_owner(interaction, self.bot.owner_id):
            return
            
        modal = TextEditModal(
            title="Edit Description",
            current_text=self.bot.character_description
        )

        async def on_submit(modal_interaction: discord.Interaction) -> None:
            self.bot.character_description = modal.text_input.value
            self.bot.config_manager_obj.save_config()
            await modal_interaction.response.send_message(
                "Character description updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def edit_scenario(self, interaction: discord.Interaction) -> None:
        if not await PermissionValidator.validate_owner(interaction, self.bot.owner_id):
            return
            
        modal = TextEditModal(
            title="Edit Scenario",
            current_text=self.bot.character_scenario
        )

        async def on_submit(modal_interaction: discord.Interaction) -> None:
            self.bot.character_scenario = modal.text_input.value
            self.bot.config_manager_obj.save_config()
            await modal_interaction.response.send_message(
                "Character scenario updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

class BlacklistManager:
    def __init__(self, bot: Any):
        self.bot = bot
        
    def get_options(self) -> List[discord.SelectOption]:
        return [
            discord.SelectOption(label="View Blacklist", value=BlacklistOption.VIEW),
            discord.SelectOption(label="Add User", value=BlacklistOption.ADD_USER),
            discord.SelectOption(label="Remove User", value=BlacklistOption.REMOVE_USER),
        ]
        
    async def view_blacklist(self, interaction: discord.Interaction) -> None:
        if not self.bot.blacklisted_users:
            await interaction.response.send_message(
                "No users are blacklisted.", ephemeral=True
            )
            return

        blacklist_display = "**Blacklisted Users:**\n"
        for user_id in self.bot.blacklisted_users:
            user = self.bot.get_user(user_id)
            name = user.name if user else f"Unknown User ({user_id})"
            blacklist_display += f"- {name} ({user_id})\n"

        await interaction.response.send_message(
            blacklist_display, ephemeral=True
        )
        
    async def add_user_to_blacklist(self, interaction: discord.Interaction) -> None:
        modal = UserIDModal(title="Add User to Blacklist")

        async def on_user_submit(modal_interaction: discord.Interaction) -> None:
            try:
                user_id = int(modal.user_id_input.value)
                if user_id not in self.bot.blacklisted_users:
                    self.bot.blacklisted_users.append(user_id)
                    self.bot.config_manager_obj.save_config()
                    await modal_interaction.response.send_message(
                        f"User {user_id} added to blacklist.", ephemeral=True
                    )
                else:
                    await modal_interaction.response.send_message(
                        "User is already blacklisted.", ephemeral=True
                    )
            except ValueError:
                await modal_interaction.response.send_message(
                    "Invalid user ID. Please enter a valid number.",
                    ephemeral=True,
                )

        modal.on_submit = on_user_submit
        await interaction.response.send_modal(modal)
        
    async def remove_user_from_blacklist(self, interaction: discord.Interaction) -> None:
        if not self.bot.blacklisted_users:
            await interaction.response.send_message(
                "No users are blacklisted.", ephemeral=True
            )
            return

        modal = UserIDModal(title="Remove User from Blacklist")

        async def on_user_submit(modal_interaction: discord.Interaction) -> None:
            try:
                user_id = int(modal.user_id_input.value)
                if user_id in self.bot.blacklisted_users:
                    self.bot.blacklisted_users.remove(user_id)
                    self.bot.config_manager_obj.save_config()
                    await modal_interaction.response.send_message(
                        f"User {user_id} removed from blacklist.",
                        ephemeral=True,
                    )
                else:
                    await modal_interaction.response.send_message(
                        "User is not in the blacklist.", ephemeral=True
                    )
            except ValueError:
                await modal_interaction.response.send_message(
                    "Invalid user ID. Please enter a valid number.",
                    ephemeral=True,
                )

        modal.on_submit = on_user_submit
        await interaction.response.send_modal(modal)
        
    async def handle_blacklist_action(self, interaction: discord.Interaction, action: str) -> None:
        if action == BlacklistOption.VIEW:
            await self.view_blacklist(interaction)
        elif action == BlacklistOption.ADD_USER:
            await self.add_user_to_blacklist(interaction)
        elif action == BlacklistOption.REMOVE_USER:
            await self.remove_user_from_blacklist(interaction)

class DataPersistenceManager:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def save_all_data(self, interaction: discord.Interaction) -> None:
        if not await PermissionValidator.validate_owner(interaction, self.bot.owner_id):
            return
            
        self.bot.config_manager_obj.save_config()
        if hasattr(self.bot, 'memory_manager'):
            self.bot.memory_manager._save_memory()
        if hasattr(self.bot, 'lorebook_manager'):
            self.bot.lorebook_manager._save_lorebook()
            
        await interaction.response.send_message(
            "All data and settings saved!", ephemeral=True
        )

class SettingsCommandHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def handle_settings(self, interaction: discord.Interaction) -> None:
        settings_display = SettingsFormatter.format_settings(self.bot)
        
        if interaction.user.id != self.bot.owner_id:
            await interaction.response.send_message(settings_display)
            return
            
        view = SettingsView(self.bot)
        await interaction.response.send_message(settings_display, view=view)

class BlacklistCommandHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        self.blacklist_manager = BlacklistManager(bot)
        
    async def handle_blacklist(self, interaction: discord.Interaction) -> None:
        if not await PermissionValidator.validate_owner(interaction, self.bot.owner_id):
            return

        options = self.blacklist_manager.get_options()
        select = discord.ui.Select(placeholder="Select Action", options=options)

        async def select_callback(select_interaction: discord.Interaction) -> None:
            action = select.values[0]
            await self.blacklist_manager.handle_blacklist_action(select_interaction, action)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            "Blacklist Management:", view=view, ephemeral=True
        )

class RegexCommandHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def handle_regex_command(self, interaction: discord.Interaction) -> None:
        if not await PermissionValidator.validate_owner(interaction, self.bot.owner_id):
            await interaction.response.send_message(
                "Only the bot owner can manage RegEx scripts.", ephemeral=True
            )
            return
            
        view = RegexManagementView(self.bot.regex_manager)
        embed = await view.generate_embed(interaction)
        
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

class HelpEmbedBuilder:
    def __init__(self, bot: Any):
        self.bot = bot
        self.color = 0x5865F2
        
    def add_basic_interaction_field(self, embed: discord.Embed) -> None:
        embed.add_field(
            name="💬 Basic Interaction",
            value=(
                "• **In activated channels:** I respond to all messages automatically\n"
                "• **In other channels:** @ mention me or say my name\n"
                "• **Reactions:** Use 🗑️ to delete my messages, ♻️ to regenerate responses"
            ),
            inline=False
        )
        
    def add_character_features_field(self, embed: discord.Embed) -> None:
        embed.add_field(
            name="🎭 Character Features",
            value=(
                "• `/character_info` - View my description, traits, and backstory\n"
                "• `/activate` - Make me respond to all messages in a channel\n"
                "• `/deactivate` - I'll only respond when mentioned or called by name"
            ),
            inline=False
        )
        
    def add_memory_system_field(self, embed: discord.Embed) -> None:
        embed.add_field(
            name="🧠 Memory System",
            value=(
                "• I remember important information from our conversations\n"
                "• `/memory` - View what I've remembered\n"
                "• `/sleep` - Process recent conversations into long-term memories"
            ),
            inline=False
        )
        
    def add_lorebook_field(self, embed: discord.Embed) -> None:
        embed.add_field(
            name="📚 Lorebook",
            value=(
                "• Custom knowledge base that influences my understanding\n"
                "• `/lorebook` - View entries in the lorebook\n"
                "• Perfect for worldbuilding and custom knowledge"
            ),
            inline=False
        )
        
    def add_owner_controls_field(self, embed: discord.Embed) -> None:
        embed.add_field(
            name="⚙️ Owner Controls",
            value=(
                "• `/settings` - Manage bot behavior settings\n"
                "• `/api_settings` - Configure AI API settings\n"
                "• `/edit_personality_traits` - Customize character traits\n"
                "• `/edit_backstory` - Change character history\n"
                "• `/edit_preferences` - Set likes and dislikes\n"
                "• `/edit_prompt` - Change system prompt (server specific)\n"
                "• `/edit_description` - Modify character description (server specific)\n"
                "• `/edit_scenario` - Set interaction scenario (server specific)\n"
                "• `/regex` - Manage text pattern manipulation\n"
                "• `/blacklist` - Manage user access (server specific)\n"
                "• `/save` - Save all current data (server specific)"
            ),
            inline=False
        )
        
    def add_ooc_commands_field(self, embed: discord.Embed) -> None:
        embed.add_field(
            name="🎬 Out-of-Character Commands",
            value=(
                "**Use `//` or `/ooc` prefix:**\n"
                "• `//memory` commands - Manage memories\n"
                "• `//lore` commands - Manage lorebook entries\n"
                "• `//regex` commands - Test and toggle regex patterns\n"
                "• `//activate` / `//deactivate` - Quick channel toggle\n"
                "• `//persona` - View current persona details\n"
                "• `//help` - Show OOC command list\n"
                "• `//save` - Save all data"
            ),
            inline=False
        )
        
    def add_tips_field(self, embed: discord.Embed) -> None:
        embed.add_field(
            name="💡 Tips for Best Results",
            value=(
                "• Ask me about topics related to my character for more immersive responses\n"
                "• Use memory and lorebook features to build consistent interactions\n"
                "• For complex tasks, be clear and specific in your instructions\n"
                "• Use `/character_info` to learn more about my personality\n"
                "• For technical help or to report issues, contact the bot owner"
            ),
            inline=False
        )
        
    def build_help_embed(self, is_owner: bool) -> discord.Embed:
        embed = discord.Embed(
            title=f"🤖 {self.bot.character_name} Help Guide",
            description=f"Welcome to the {self.bot.character_name} bot! Here's how to interact with me and make the most of my features.",
            color=self.color
        )
        
        self.add_basic_interaction_field(embed)
        self.add_character_features_field(embed)
        self.add_memory_system_field(embed)
        self.add_lorebook_field(embed)
        
        if is_owner:
            self.add_owner_controls_field(embed)
            self.add_ooc_commands_field(embed)
            
        self.add_tips_field(embed)
        
        embed.set_footer(text="OpenShapes v0.1 | Designed in https://discord.gg/8QSYftf48j")
        
        return embed

class HelpCommandHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        self.embed_builder = HelpEmbedBuilder(bot)
        
    async def handle_help_command(self, interaction: discord.Interaction) -> None:
        is_owner = interaction.user.id == self.bot.owner_id
        embed = self.embed_builder.build_help_embed(is_owner)
        await interaction.response.send_message(embed=embed)

async def edit_prompt_command(self, interaction: discord.Interaction) -> None:
    editor = CharacterEditor(self)
    await editor.edit_prompt(interaction)

async def edit_description_command(self, interaction: discord.Interaction) -> None:
    editor = CharacterEditor(self)
    await editor.edit_description(interaction)

async def edit_scenario_command(self, interaction: discord.Interaction) -> None:
    editor = CharacterEditor(self)
    await editor.edit_scenario(interaction)

async def blacklist_command(self, interaction: discord.Interaction) -> None:
    handler = BlacklistCommandHandler(self)
    await handler.handle_blacklist(interaction)

async def save_command(self, interaction: discord.Interaction) -> None:
    manager = DataPersistenceManager(self)
    await manager.save_all_data(interaction)

async def settings_command(self, interaction: discord.Interaction) -> None:
    handler = SettingsCommandHandler(self)
    await handler.handle_settings(interaction)

async def regex_command(self, interaction: discord.Interaction) -> None:
    handler = RegexCommandHandler(self)
    await handler.handle_regex_command(interaction)

async def openshape_help_command(self, interaction: discord.Interaction) -> None:
    handler = HelpCommandHandler(self)
    await handler.handle_help_command(interaction)