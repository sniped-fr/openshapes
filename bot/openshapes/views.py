import re
import discord
from typing import Callable, Optional, Protocol, TypeVar, Any, List, Awaitable
from abc import abstractmethod
from enum import Enum, auto
from discord import ui
import logging

logger = logging.getLogger("openshape.ui")

T = TypeVar('T')
InteractionCallbackT = Callable[[discord.Interaction], Awaitable[None]]

class TextInputType(Enum):
    PARAGRAPH = auto()
    SHORT = auto()
    
    @property
    def discord_style(self) -> discord.TextStyle:
        if self == TextInputType.PARAGRAPH:
            return discord.TextStyle.paragraph
        return discord.TextStyle.short

class ButtonType(Enum):
    PRIMARY = auto()
    SECONDARY = auto()
    SUCCESS = auto()
    DANGER = auto()
    
    @property
    def discord_style(self) -> discord.ButtonStyle:
        mapping = {
            ButtonType.PRIMARY: discord.ButtonStyle.primary,
            ButtonType.SECONDARY: discord.ButtonStyle.secondary,
            ButtonType.SUCCESS: discord.ButtonStyle.green,
            ButtonType.DANGER: discord.ButtonStyle.red
        }
        return mapping[self]

class UIBuilder(Protocol):
    def build(self) -> Any:
        pass

class ModalBuilder(UIBuilder):
    @abstractmethod
    def add_text_input(
        self,
        label: str,
        style: TextInputType,
        default: str = "",
        placeholder: str = "",
        required: bool = True,
        max_length: int = 0
    ) -> 'ModalBuilder':
        pass
        
    @abstractmethod
    def set_title(self, title: str) -> 'ModalBuilder':
        pass
        
    @abstractmethod
    def set_submit_callback(self, callback: InteractionCallbackT) -> 'ModalBuilder':
        pass

class TextInputBuilder:
    def __init__(self):
        self.label: str = ""
        self.style: TextInputType = TextInputType.SHORT
        self.default: str = ""
        self.placeholder: str = ""
        self.required: bool = True
        self.max_length: int = 0
        
    def with_label(self, label: str) -> 'TextInputBuilder':
        self.label = label
        return self
        
    def with_style(self, style: TextInputType) -> 'TextInputBuilder':
        self.style = style
        return self
        
    def with_default(self, default: str) -> 'TextInputBuilder':
        self.default = default
        return self
        
    def with_placeholder(self, placeholder: str) -> 'TextInputBuilder':
        self.placeholder = placeholder
        return self
        
    def with_required(self, required: bool) -> 'TextInputBuilder':
        self.required = required
        return self
        
    def with_max_length(self, max_length: int) -> 'TextInputBuilder':
        self.max_length = max_length
        return self
        
    def build(self) -> ui.TextInput:
        text_input = ui.TextInput(
            label=self.label,
            style=self.style.discord_style,
            default=self.default,
            placeholder=self.placeholder,
            required=self.required
        )
        
        if self.max_length > 0:
            text_input.max_length = self.max_length
            
        return text_input

class DiscordModalBuilder(ModalBuilder):
    def __init__(self):
        self.title: str = "Modal"
        self.inputs: List[ui.TextInput] = []
        self.submit_callback: Optional[InteractionCallbackT] = None
        
    def set_title(self, title: str) -> 'DiscordModalBuilder':
        self.title = title
        return self
        
    def add_text_input(
        self,
        label: str,
        style: TextInputType,
        default: str = "",
        placeholder: str = "",
        required: bool = True,
        max_length: int = 0
    ) -> 'DiscordModalBuilder':
        text_input = TextInputBuilder() \
            .with_label(label) \
            .with_style(style) \
            .with_default(default) \
            .with_placeholder(placeholder) \
            .with_required(required) \
            .with_max_length(max_length) \
            .build()
            
        self.inputs.append(text_input)
        return self
        
    def set_submit_callback(self, callback: InteractionCallbackT) -> 'DiscordModalBuilder':
        self.submit_callback = callback
        return self
        
    def build(self) -> ui.Modal:
        modal = ui.Modal(title=self.title)
        
        for text_input in self.inputs:
            modal.add_item(text_input)
            
        if self.submit_callback:
            modal.on_submit = self.submit_callback
            
        return modal

class TextEditModal(ui.Modal):
    def __init__(self, title: str, current_text: str = "", max_length: int = 4000):
        super().__init__(title=title)
        self.text_input = TextInputBuilder() \
            .with_label("Edit Text") \
            .with_style(TextInputType.PARAGRAPH) \
            .with_default(current_text) \
            .with_max_length(max_length) \
            .with_required(True) \
            .build()
        self.add_item(self.text_input)

class APISettingModal(ui.Modal):
    def __init__(self, title: str):
        super().__init__(title=title)
        self.setting_input = TextInputBuilder() \
            .with_label("Value") \
            .with_style(TextInputType.SHORT) \
            .with_required(True) \
            .build()
        self.add_item(self.setting_input)

class UserIDModal(ui.Modal):
    def __init__(self, title: str):
        super().__init__(title=title)
        self.user_id_input = TextInputBuilder() \
            .with_label("User ID") \
            .with_style(TextInputType.SHORT) \
            .with_placeholder("Enter user ID (e.g. 123456789012345678)") \
            .with_required(True) \
            .build()
        self.add_item(self.user_id_input)

class ButtonConfiguration:
    def __init__(
        self,
        label: str,
        style: ButtonType,
        callback: InteractionCallbackT,
        custom_id: Optional[str] = None
    ):
        self.label = label
        self.style = style
        self.callback = callback
        self.custom_id = custom_id
        
    @staticmethod
    def confirm_button(callback: InteractionCallbackT) -> 'ButtonConfiguration':
        return ButtonConfiguration("Confirm", ButtonType.SUCCESS, callback)
        
    @staticmethod
    def cancel_button(callback: InteractionCallbackT) -> 'ButtonConfiguration':
        return ButtonConfiguration("Cancel", ButtonType.DANGER, callback)

class ViewBuilder(UIBuilder):
    def __init__(self):
        self.buttons: List[ButtonConfiguration] = []
        self.timeout: int = 180
        
    def with_timeout(self, timeout: int) -> 'ViewBuilder':
        self.timeout = timeout
        return self
        
    def add_button(self, config: ButtonConfiguration) -> 'ViewBuilder':
        self.buttons.append(config)
        return self
        
    def build(self) -> ui.View:
        view = ui.View(timeout=self.timeout)
        
        for config in self.buttons:
            button = ui.Button(
                label=config.label,
                style=config.style.discord_style,
                custom_id=config.custom_id
            )
            button.callback = config.callback
            view.add_item(button)
            
        return view

class ConfirmView(ui.View):
    def __init__(
        self,
        confirm_callback: InteractionCallbackT,
        cancel_callback: Optional[InteractionCallbackT] = None
    ):
        super().__init__(timeout=180)
        self.confirm_callback = confirm_callback
        self.cancel_callback = cancel_callback

        @ui.button(label="Confirm", style=discord.ButtonStyle.green)
        async def confirm(self, interaction: discord.Interaction, button: ui.Button) -> None:
            await self.confirm_callback(interaction)
            self.stop()

        @ui.button(label="Cancel", style=discord.ButtonStyle.red)
        async def cancel(self, interaction: discord.Interaction, button: ui.Button) -> None:
            if self.cancel_callback:
                await self.cancel_callback(interaction)
            else:
                await interaction.response.send_message("Operation canceled.", ephemeral=True)
            self.stop()

        self.confirm = confirm.__get__(self)
        self.cancel = cancel.__get__(self)

class LorebookEntryModal(ui.Modal):
    def __init__(self, title: str, default_keyword: str = "", default_content: str = ""):
        super().__init__(title=title)
        self.keyword_input = ui.TextInput(
            label="Keyword",
            style=discord.TextStyle.short,
            default=default_keyword,
            placeholder="Enter a keyword or phrase that triggers this information",
            required=True,
        )
        self.add_item(self.keyword_input)

        self.content_input = ui.TextInput(
            label="Content",
            style=discord.TextStyle.paragraph,
            default=default_content,
            placeholder="Enter the information to associate with this keyword",
            max_length=2000,
            required=True,
        )
        self.add_item(self.content_input)

class LorebookManagementView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @ui.button(label="Add Entry", style=discord.ButtonStyle.green)
    async def add_entry(self, interaction: discord.Interaction, button: ui.Button):
        modal = LorebookEntryModal(title="Add Lorebook Entry")

        async def on_submit(modal_interaction):
            keyword = modal.keyword_input.value
            content = modal.content_input.value
            
            self.bot.lorebook_manager.add_entry(keyword, content)
            
            await modal_interaction.response.send_message(
                f"Lorebook entry added for keyword: '{keyword}'", ephemeral=True
            )
            
            lore_display = self.bot.lorebook_manager.format_entries_for_display()
            await interaction.message.edit(content=lore_display, view=self)

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @ui.button(label="Edit Entry", style=discord.ButtonStyle.primary)
    async def edit_entry(self, interaction: discord.Interaction, button: ui.Button):
        entries = self.bot.lorebook_manager.get_entries()
        
        if not entries:
            await interaction.response.send_message("No lorebook entries exist yet.", ephemeral=True)
            return
            
        options = [
            discord.SelectOption(
                label=f"{i+1}. {entry['keyword'][:80]}", 
                value=str(i),
                description=entry['content'][:100] + "..." if len(entry['content']) > 100 else entry['content']
            )
            for i, entry in enumerate(entries)
        ]
        
        select = ui.Select(
            placeholder="Select an entry to edit",
            options=options[:25]
        )

        async def select_callback(select_interaction):
            index = int(select.values[0])
            entry = entries[index]
            
            modal = LorebookEntryModal(
                title="Edit Lorebook Entry",
                default_keyword=entry["keyword"],
                default_content=entry["content"]
            )

            async def on_submit(modal_interaction):
                self.bot.lorebook_manager.update_entry(
                    index, modal.keyword_input.value, modal.content_input.value
                )
                
                await modal_interaction.response.send_message(
                    "Lorebook entry updated!", ephemeral=True
                )
                
                lore_display = self.bot.lorebook_manager.format_entries_for_display()
                await interaction.message.edit(content=lore_display, view=self)

            modal.on_submit = on_submit
            await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(label="Remove Entry", style=discord.ButtonStyle.danger)
    async def remove_entry(self, interaction: discord.Interaction, button: ui.Button):
        entries = self.bot.lorebook_manager.get_entries()
        
        if not entries:
            await interaction.response.send_message("No lorebook entries exist yet.", ephemeral=True)
            return
            
        options = [
            discord.SelectOption(
                label=f"{i+1}. {entry['keyword'][:80]}", 
                value=str(i)
            )
            for i, entry in enumerate(entries)
        ]
        
        select = ui.Select(
            placeholder="Select an entry to remove",
            options=options[:25]
        )

        async def select_callback(select_interaction):
            index = int(select.values[0])
            entry = entries[index]
            
            async def confirm_callback(confirm_interaction):
                self.bot.lorebook_manager.remove_entry(index)
                
                await confirm_interaction.response.send_message(
                    f"Removed lorebook entry for '{entry['keyword']}'", ephemeral=True
                )
                
                lore_display = self.bot.lorebook_manager.format_entries_for_display()
                await interaction.message.edit(content=lore_display, view=self)

            confirm_view = ConfirmView(confirm_callback=confirm_callback)
            await select_interaction.response.send_message(
                f"Are you sure you want to remove the entry for '{entry['keyword']}'?",
                view=confirm_view,
                ephemeral=True
            )

        select.callback = select_callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

class SettingsView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @ui.button(label="Toggle Name in Responses", style=discord.ButtonStyle.primary)
    async def toggle_name(self, interaction: discord.Interaction, button: ui.Button):
        self.bot.add_character_name = not self.bot.add_character_name
        self.bot.config_manager.update_field("add_character_name", self.bot.add_character_name)
        
        settings_display = f"**{self.bot.character_name} Settings:**\n"
        settings_display += f"- Add name to responses: {'Enabled' if self.bot.add_character_name else 'Disabled'}\n"
        settings_display += f"- Reply to mentions: {'Enabled' if self.bot.always_reply_mentions else 'Disabled'}\n"
        settings_display += f"- Reply when name is called: {'Enabled' if self.bot.reply_to_name else 'Disabled'}\n"
        
        await interaction.response.edit_message(content=settings_display, view=self)

    @ui.button(label="Toggle Reply to Mentions", style=discord.ButtonStyle.primary)
    async def toggle_mentions(self, interaction: discord.Interaction, button: ui.Button):
        self.bot.always_reply_mentions = not self.bot.always_reply_mentions
        self.bot.config_manager.update_field("always_reply_mentions", self.bot.always_reply_mentions)
        
        settings_display = f"**{self.bot.character_name} Settings:**\n"
        settings_display += f"- Add name to responses: {'Enabled' if self.bot.add_character_name else 'Disabled'}\n"
        settings_display += f"- Reply to mentions: {'Enabled' if self.bot.always_reply_mentions else 'Disabled'}\n"
        settings_display += f"- Reply when name is called: {'Enabled' if self.bot.reply_to_name else 'Disabled'}\n"
        
        await interaction.response.edit_message(content=settings_display, view=self)

    @ui.button(label="Toggle Reply to Name", style=discord.ButtonStyle.primary)
    async def toggle_name_reply(self, interaction: discord.Interaction, button: ui.Button):
        self.bot.reply_to_name = not self.bot.reply_to_name
        self.bot.config_manager.update_field("reply_to_name", self.bot.reply_to_name)
        
        settings_display = f"**{self.bot.character_name} Settings:**\n"
        settings_display += f"- Add name to responses: {'Enabled' if self.bot.add_character_name else 'Disabled'}\n"
        settings_display += f"- Reply to mentions: {'Enabled' if self.bot.always_reply_mentions else 'Disabled'}\n"
        settings_display += f"- Reply when name is called: {'Enabled' if self.bot.reply_to_name else 'Disabled'}\n"
        
        await interaction.response.edit_message(content=settings_display, view=self)

class RegexScriptModal(ui.Modal):
    def __init__(
        self,
        title: str,
        default_name: str = "",
        default_pattern: str = "",
        default_replace: str = ""
    ):
        super().__init__(title=title)
        self.name_input = ui.TextInput(
            label="Script Name",
            style=discord.TextStyle.short,
            default=default_name,
            placeholder="Enter a name for this regex script",
            required=True,
        )
        self.add_item(self.name_input)

        self.pattern_input = ui.TextInput(
            label="Find Pattern (RegEx)",
            style=discord.TextStyle.paragraph,
            default=default_pattern,
            placeholder="Enter regex pattern to match",
            required=True,
        )
        self.add_item(self.pattern_input)
        
        self.replace_input = ui.TextInput(
            label="Replace With",
            style=discord.TextStyle.paragraph,
            default=default_replace,
            placeholder="Enter replacement text (can include regex groups like $1, $2)",
            required=True,
        )
        self.add_item(self.replace_input)

class RegexManagementView(ui.View):
    def __init__(self, regex_manager):
        super().__init__(timeout=300)
        self.regex_manager = regex_manager
        
    async def generate_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="RegEx Pattern Manager",
            description="Manage regular expression scripts for text manipulation",
            color=discord.Color.blue()
        )
        
        if self.regex_manager.scripts:
            scripts_text = ""
            for i, script in enumerate(self.regex_manager.scripts, 1):
                status = "✅" if not script.disabled else "❌"
                scripts_text += f"{i}. {status} **{script.name}**\n"
            embed.add_field(name="Scripts", value=scripts_text, inline=False)
        else:
            embed.add_field(name="Scripts", value="No scripts", inline=False)
            
        return embed

    @ui.button(label="Add Script", style=discord.ButtonStyle.green)
    async def add_script(self, interaction: discord.Interaction, button: ui.Button):
        modal = RegexScriptModal(title="Add RegEx Script")

        async def on_submit(modal_interaction):
            name = modal.name_input.value
            pattern = modal.pattern_input.value
            replace = modal.replace_input.value
            
            if self.regex_manager.get_script(name) is not None:
                await modal_interaction.response.send_message(
                    f"A script with the name '{name}' already exists.", ephemeral=True
                )
                return
                
            try:
                re.compile(pattern)
            except re.error as e:
                await modal_interaction.response.send_message(
                    f"Invalid regex pattern: {e}", ephemeral=True
                )
                return
                
            self.regex_manager.add_script(name, pattern, replace)
            
            await modal_interaction.response.send_message(
                f"Added regex script: '{name}'", ephemeral=True
            )
            
            embed = await self.generate_embed(interaction)
            try:
                await interaction.message.edit(embed=embed, view=self)
            except discord.errors.NotFound:
                # Message no longer exists, send a new message
                await modal_interaction.followup.send(
                    "The original message was not found. Here's the updated view:", 
                    embed=embed, 
                    view=self, 
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"Error updating message: {e}")

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @ui.button(label="Edit Script", style=discord.ButtonStyle.primary)
    async def edit_script(self, interaction: discord.Interaction, button: ui.Button):
        if not self.regex_manager.scripts:
            await interaction.response.send_message("No scripts exist yet.", ephemeral=True)
            return
            
        options = [
            discord.SelectOption(
                label=f"{script.name[:80]}", 
                value=script.name
            )
            for script in self.regex_manager.scripts
        ]
        
        select = ui.Select(
            placeholder="Select a script to edit",
            options=options[:25]
        )

        async def select_callback(select_interaction):
            script_name = select.values[0]
            script = self.regex_manager.get_script(script_name)
            
            if not script:
                await select_interaction.response.send_message(
                    "Script not found.", ephemeral=True
                )
                return
                
            modal = RegexScriptModal(
                title="Edit RegEx Script",
                default_name=script.name,
                default_pattern=script.config.find_pattern,
                default_replace=script.config.replace_with
            )

            async def on_submit(modal_interaction):
                try:
                    re.compile(modal.pattern_input.value)
                except re.error as e:
                    await modal_interaction.response.send_message(
                        f"Invalid regex pattern: {e}", ephemeral=True
                    )
                    return

                # Check if the name changed - if so, need to handle differently
                if script.name != modal.name_input.value:
                    # Create a new script with the new name and delete the old one
                    self.regex_manager.add_script(
                        modal.name_input.value,
                        modal.pattern_input.value,
                        modal.replace_input.value
                    )
                    self.regex_manager.remove_script(script.name)
                else:
                    # Just update the pattern and replacement
                    script.config.find_pattern = modal.pattern_input.value
                    script.config.replace_with = modal.replace_input.value
                
                self.regex_manager.save_scripts()
                
                await modal_interaction.response.send_message(
                    f"Updated regex script: '{modal.name_input.value}'", ephemeral=True
                )
                
                embed = await self.generate_embed(interaction)
                try:
                    await interaction.message.edit(embed=embed, view=self)
                except discord.errors.NotFound:
                    # Message no longer exists, send a new message
                    await modal_interaction.followup.send(
                        "The original message was not found. Here's the updated view:", 
                        embed=embed, 
                        view=self, 
                        ephemeral=True
                    )
                except Exception as e:
                    logger.error(f"Error updating message: {e}")

            modal.on_submit = on_submit
            await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(label="Toggle Script", style=discord.ButtonStyle.secondary)
    async def toggle_script(self, interaction: discord.Interaction, button: ui.Button):
        if not self.regex_manager.scripts:
            await interaction.response.send_message("No scripts exist yet.", ephemeral=True)
            return
            
        options = [
            discord.SelectOption(
                label=f"{'✅' if not script.disabled else '❌'} {script.name[:80]}", 
                value=script.name
            )
            for script in self.regex_manager.scripts
        ]
        
        select = ui.Select(
            placeholder="Select a script to toggle",
            options=options[:25]
        )

        async def select_callback(select_interaction):
            script_name = select.values[0]
            script = self.regex_manager.get_script(script_name)
            
            if not script:
                await select_interaction.response.send_message(
                    "Script not found.", ephemeral=True
                )
                return
                
            script.disabled = not script.disabled
            self.regex_manager.save_scripts()
            
            status = "disabled" if script.disabled else "enabled"
            await select_interaction.response.send_message(
                f"Script '{script.name}' is now {status}.", ephemeral=True
            )
            
            embed = await self.generate_embed(interaction)
            try:
                await interaction.message.edit(embed=embed, view=self)
            except discord.errors.NotFound:
                # Message no longer exists, send a new message
                await select_interaction.followup.send(
                    "The original message was not found. Here's the updated view:", 
                    embed=embed, 
                    view=self, 
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"Error updating message: {e}")

        select.callback = select_callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(label="Remove Script", style=discord.ButtonStyle.danger)
    async def remove_script(self, interaction: discord.Interaction, button: ui.Button):
        if not self.regex_manager.scripts:
            await interaction.response.send_message("No scripts exist yet.", ephemeral=True)
            return
            
        options = [
            discord.SelectOption(
                label=f"{script.name[:80]}", 
                value=script.name
            )
            for script in self.regex_manager.scripts
        ]
        
        select = ui.Select(
            placeholder="Select a script to remove",
            options=options[:25]
        )

        async def select_callback(select_interaction):
            script_name = select.values[0]
            
            # Create a direct confirmation view with buttons
            confirm_view = discord.ui.View(timeout=60)
            
            confirm_button = discord.ui.Button(
                label="Yes, Remove Script", 
                style=discord.ButtonStyle.danger
            )
            cancel_button = discord.ui.Button(
                label="Cancel", 
                style=discord.ButtonStyle.secondary
            )
            
            async def confirm_button_callback(confirm_interaction):
                if self.regex_manager.remove_script(script_name):
                    await confirm_interaction.response.send_message(
                        f"Removed regex script: '{script_name}'", ephemeral=True
                    )
                    
                    embed = await self.generate_embed(interaction)
                    try:
                        await interaction.message.edit(embed=embed, view=self)
                    except discord.errors.NotFound:
                        # Message no longer exists, send a new message
                        await confirm_interaction.followup.send(
                            "The original message was not found. Here's the updated view:", 
                            embed=embed, 
                            view=self, 
                            ephemeral=True
                        )
                    except Exception as e:
                        logger.error(f"Error updating message: {e}")
                else:
                    await confirm_interaction.response.send_message(
                        f"Script '{script_name}' not found.", ephemeral=True
                    )
            
            async def cancel_button_callback(cancel_interaction):
                await cancel_interaction.response.send_message(
                    "Remove operation canceled.", ephemeral=True
                )
            
            confirm_button.callback = confirm_button_callback
            cancel_button.callback = cancel_button_callback
            
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)
            
            await select_interaction.response.send_message(
                f"Are you sure you want to remove the script '{script_name}'?",
                view=confirm_view,
                ephemeral=True
            )

        select.callback = select_callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(label="View Settings", style=discord.ButtonStyle.primary)
    async def view_settings(self, interaction: discord.Interaction, button: ui.Button):
        if not self.regex_manager.scripts:
            await interaction.response.send_message("No scripts exist yet.", ephemeral=True)
            return
            
        options = [
            discord.SelectOption(
                label=f"{script.name[:80]}", 
                value=script.name
            )
            for script in self.regex_manager.scripts
        ]
        
        select = ui.Select(
            placeholder="Select a script to view settings",
            options=options[:25]
        )

        async def select_callback(select_interaction):
            script_name = select.values[0]
            script = self.regex_manager.get_script(script_name)
            
            if not script:
                await select_interaction.response.send_message(
                    "Script not found.", ephemeral=True
                )
                return
                
            settings_embed = discord.Embed(
                title=f"RegEx Script: {script.name}",
                color=discord.Color.blue()
            )
            
            settings_embed.add_field(
                name="Pattern", 
                value=f"```{script.config.find_pattern}```", 
                inline=False
            )
            settings_embed.add_field(
                name="Replacement", 
                value=f"```{script.config.replace_with}```", 
                inline=False
            )
            
            if hasattr(script.config, 'trim_out') and script.config.trim_out:
                settings_embed.add_field(
                    name="Trim Out", 
                    value=f"```{script.config.trim_out}```", 
                    inline=False
                )
                
            affected_types = []
            # Get method to check what text types the script affects
            if hasattr(script, 'applies_to_text_type'):
                from openshapes.utils.regex_extension import TextType
                
                if script.applies_to_text_type(TextType.USER_INPUT):
                    affected_types.append("User Input")
                if script.applies_to_text_type(TextType.AI_RESPONSE):
                    affected_types.append("AI Response")
                if script.applies_to_text_type(TextType.SLASH_COMMAND):
                    affected_types.append("Slash Commands")
                if script.applies_to_text_type(TextType.WORLD_INFO):
                    affected_types.append("World Info")
                if script.applies_to_text_type(TextType.REASONING):
                    affected_types.append("Reasoning")
            
            settings_embed.add_field(
                name="Affects", 
                value=", ".join(affected_types) if affected_types else "None", 
                inline=True
            )
            settings_embed.add_field(
                name="Status", 
                value="Enabled" if not script.disabled else "Disabled", 
                inline=True
            )
            
            await select_interaction.response.send_message(
                embed=settings_embed, ephemeral=True
            )

        select.callback = select_callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)