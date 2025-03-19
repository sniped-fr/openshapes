import discord, datetime

# Add the APISettingModal class
class APISettingModal(discord.ui.Modal):
    """Modal for entering API settings"""

    def __init__(self, title: str):
        super().__init__(title=title)
        self.setting_input = discord.ui.TextInput(
            label="Value:",
            placeholder="Enter the setting value",
            max_length=500,
        )
        self.add_item(self.setting_input)


class TextEditModal(discord.ui.Modal):
    """Modal for editing text fields"""

    def __init__(self, title: str, current_text: str):
        super().__init__(title=title)
        self.text_input = discord.ui.TextInput(
            label="Enter new text:",
            style=discord.TextStyle.paragraph,
            default=current_text,
            max_length=2000,
        )
        self.add_item(self.text_input)


class UserIDModal(discord.ui.Modal):
    """Modal for entering a user ID"""

    def __init__(self, title: str):
        super().__init__(title=title)
        self.user_id_input = discord.ui.TextInput(
            label="User ID:",
            placeholder="Enter the user ID (numbers only)",
            max_length=20,
        )
        self.add_item(self.user_id_input)


class LorebookEntryModal(discord.ui.Modal):
    """Modal for adding lorebook entries"""

    def __init__(self, title: str):
        super().__init__(title=title)
        self.keyword_input = discord.ui.TextInput(
            label="Trigger Keyword:",
            placeholder="Enter the keyword that will trigger this lore",
            max_length=100,
        )
        self.content_input = discord.ui.TextInput(
            label="Lore Content:",
            style=discord.TextStyle.paragraph,
            placeholder="Enter the information for this lorebook entry",
            max_length=2000,
        )
        self.add_item(self.keyword_input)
        self.add_item(self.content_input)


class MemoryManagementView(discord.ui.View):
    """View for managing character memory"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(label="Add Memory", style=discord.ButtonStyle.primary)
    async def add_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MemoryEntryModal()

        async def on_submit(modal_interaction):
            topic = modal.topic_input.value
            details = modal.details_input.value
            
            # Store memory with user attribution
            self.bot.long_term_memory[topic] = {
                "detail": details,
                "source": interaction.user.display_name,  # Use the name of the person adding the memory
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            self.bot._save_memory()
            await modal_interaction.response.send_message(
                f"Added memory: {topic} (from {interaction.user.display_name})", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Clear All Memory", style=discord.ButtonStyle.danger)
    async def clear_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.long_term_memory = {}
        self.bot._save_memory()
        await interaction.response.send_message("Memory cleared!", ephemeral=True)


class MemoryEntryModal(discord.ui.Modal):
    """Modal for adding memory entries"""

    def __init__(self):
        super().__init__(title="Add Memory Entry")
        self.topic_input = discord.ui.TextInput(
            label="Topic:",
            placeholder="E.g., User Preferences, Recent Events",
            max_length=100,
        )
        self.details_input = discord.ui.TextInput(
            label="Details:",
            style=discord.TextStyle.paragraph,
            placeholder="Enter the details to remember",
            max_length=1000,
        )
        self.add_item(self.topic_input)
        self.add_item(self.details_input)


class LorebookManagementView(discord.ui.View):
    """View for managing lorebook entries"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(label="Add Entry", style=discord.ButtonStyle.primary)
    async def add_entry(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = LorebookEntryModal(title="Add Lorebook Entry")

        async def on_submit(modal_interaction):
            new_entry = {
                "keyword": modal.keyword_input.value,
                "content": modal.content_input.value,
            }
            self.bot.lorebook_entries.append(new_entry)
            self.bot._save_lorebook()
            await modal_interaction.response.send_message(
                f"Added lorebook entry for keyword: {new_entry['keyword']}",
                ephemeral=True,
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Clear All Entries", style=discord.ButtonStyle.danger)
    async def clear_entries(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.bot.lorebook_entries = []
        self.bot._save_lorebook()
        await interaction.response.send_message(
            "All lorebook entries cleared!", ephemeral=True
        )


class SettingsView(discord.ui.View):
    """View for toggling character settings"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(
        label="Toggle Name in Responses", style=discord.ButtonStyle.secondary
    )
    async def toggle_name(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.bot.add_character_name = not self.bot.add_character_name
        self.bot._save_config()
        await interaction.response.send_message(
            f"Character name in responses: {'Enabled' if self.bot.add_character_name else 'Disabled'}",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Toggle Reply to Name", style=discord.ButtonStyle.secondary
    )
    async def toggle_reply_name(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.bot.reply_to_name = not self.bot.reply_to_name
        self.bot._save_config()
        await interaction.response.send_message(
            f"Reply when name is called: {'Enabled' if self.bot.reply_to_name else 'Disabled'}",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Toggle Reply to Mentions", style=discord.ButtonStyle.secondary
    )
    async def toggle_mentions(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.bot.always_reply_mentions = not self.bot.always_reply_mentions
        self.bot._save_config()
        await interaction.response.send_message(
            f"Reply to @mentions: {'Enabled' if self.bot.always_reply_mentions else 'Disabled'}",
            ephemeral=True,
        )

