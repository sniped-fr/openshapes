import discord
import logging
from openshapes.utils.views import TextEditModal, UserIDModal, SettingsView, RegexManagementView

logger = logging.getLogger("openshape")

async def settings_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        settings_display = f"**{self.character_name} Settings:**\n"
        settings_display += f"- Add name to responses: {'Enabled' if self.add_character_name else 'Disabled'}\n"
        settings_display += f"- Reply to mentions: {'Enabled' if self.always_reply_mentions else 'Disabled'}\n"
        settings_display += f"- Reply when name is called: {'Enabled' if self.reply_to_name else 'Disabled'}\n"

        await interaction.response.send_message(settings_display)
        return

    view = SettingsView(self)

    settings_display = f"**{self.character_name} Settings:**\n"
    settings_display += f"- Add name to responses: {'Enabled' if self.add_character_name else 'Disabled'}\n"
    settings_display += f"- Reply to mentions: {'Enabled' if self.always_reply_mentions else 'Disabled'}\n"
    settings_display += f"- Reply when name is called: {'Enabled' if self.reply_to_name else 'Disabled'}\n"

    await interaction.response.send_message(settings_display, view=view)

async def edit_prompt_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can use this command", ephemeral=True
        )
        return

    modal = TextEditModal(
        title="Edit System Prompt", current_text=self.system_prompt
    )

    async def on_submit(modal_interaction):
        self.system_prompt = modal.text_input.value
        self.config_manager.save_config()
        await modal_interaction.response.send_message(
            "System prompt updated!", ephemeral=True
        )

    modal.on_submit = on_submit
    await interaction.response.send_modal(modal)

async def edit_description_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can use this command", ephemeral=True
        )
        return

    modal = TextEditModal(
        title="Edit Description", current_text=self.character_description
    )

    async def on_submit(modal_interaction):
        self.character_description = modal.text_input.value
        self.config_manager.save_config()
        await modal_interaction.response.send_message(
            "Character description updated!", ephemeral=True
        )

    modal.on_submit = on_submit
    await interaction.response.send_modal(modal)


async def edit_scenario_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can use this command", ephemeral=True
        )
        return

    modal = TextEditModal(
        title="Edit Scenario", current_text=self.character_scenario
    )

    async def on_submit(modal_interaction):
        self.character_scenario = modal.text_input.value
        self.config_manager.save_config()
        await modal_interaction.response.send_message(
            "Character scenario updated!", ephemeral=True
        )

    modal.on_submit = on_submit
    await interaction.response.send_modal(modal)

async def blacklist_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can use this command", ephemeral=True
        )
        return

    options = [
        discord.SelectOption(label="View Blacklist", value="view"),
        discord.SelectOption(label="Add User", value="add_user"),
        discord.SelectOption(label="Remove User", value="remove_user"),
    ]

    select = discord.ui.Select(placeholder="Select Action", options=options)

    async def select_callback(select_interaction):
        action = select.values[0]

        if action == "view":
            if not self.blacklisted_users:
                await select_interaction.response.send_message(
                    "No users are blacklisted.", ephemeral=True
                )
                return

            blacklist_display = "**Blacklisted Users:**\n"
            for user_id in self.blacklisted_users:
                user = self.get_user(user_id)
                name = user.name if user else f"Unknown User ({user_id})"
                blacklist_display += f"- {name} ({user_id})\n"

            await select_interaction.response.send_message(
                blacklist_display, ephemeral=True
            )

        elif action == "add_user":
            modal = UserIDModal(title="Add User to Blacklist")

            async def on_user_submit(modal_interaction):
                try:
                    user_id = int(modal.user_id_input.value)
                    if user_id not in self.blacklisted_users:
                        self.blacklisted_users.append(user_id)
                        self.config_manager.save_config()
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
            await select_interaction.response.send_modal(modal)

        elif action == "remove_user":
            if not self.blacklisted_users:
                await select_interaction.response.send_message(
                    "No users are blacklisted.", ephemeral=True
                )
                return

            modal = UserIDModal(title="Remove User from Blacklist")

            async def on_user_submit(modal_interaction):
                try:
                    user_id = int(modal.user_id_input.value)
                    if user_id in self.blacklisted_users:
                        self.blacklisted_users.remove(user_id)
                        self.config_manager.save_config()
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
            await select_interaction.response.send_modal(modal)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)

    await interaction.response.send_message(
        "Blacklist Management:", view=view, ephemeral=True
    )

async def save_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can use this command", ephemeral=True
        )
        return

    self.config_manager.save_config()
    self.memory_manager._save_memory()
    self.lorebook_manager._save_lorebook()

    await interaction.response.send_message(
        "All data and settings saved!", ephemeral=True
    )

async def regex_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can manage RegEx scripts.", ephemeral=True
        )
        return
        
    view = RegexManagementView(self.regex_manager)
    embed = await view.generate_embed(interaction)
    
    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True
    )

async def openshape_help_command(self, interaction: discord.Interaction):
    
    embed = discord.Embed(
        title=f"🤖 {self.character_name} Help Guide",
        description=f"Welcome to the {self.character_name} bot! Here's how to interact with me and make the most of my features.",
        color=0x5865F2
    )
    
    embed.add_field(
        name="💬 Basic Interaction",
        value=(
            "• **In activated channels:** I respond to all messages automatically\n"
            "• **In other channels:** @ mention me or say my name ('{self.character_name}')\n"
            "• **Reactions:** Use 🗑️ to delete my messages, ♻️ to regenerate responses"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎭 Character Features",
        value=(
            "• `/character_info` - View my description, traits, and backstory\n"
            "• `/activate` - Make me respond to all messages in a channel\n"
            "• `/deactivate` - I'll only respond when mentioned or called by name"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🧠 Memory System",
        value=(
            "• I remember important information from our conversations\n"
            "• `/memory` - View what I've remembered\n"
            "• `/sleep` - Process recent conversations into long-term memories"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📚 Lorebook",
        value=(
            "• Custom knowledge base that influences my understanding\n"
            "• `/lorebook` - View entries in the lorebook\n"
            "• Perfect for worldbuilding and custom knowledge"
        ),
        inline=False
    )
    
    if interaction.user.id == self.owner_id:
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
    
    if interaction.user.id == self.owner_id:
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
    
    embed.set_footer(text="OpenShapes v0.1 | Designed in https://discord.gg/8QSYftf48j")
    
    await interaction.response.send_message(embed=embed)
