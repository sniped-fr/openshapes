import discord
import re
from discord import ui
from typing import Callable

class TextEditModal(ui.Modal):
    def __init__(self, title: str, current_text: str = "", max_length: int = 4000):
        super().__init__(title=title)
        self.text_input = ui.TextInput(
            label="Edit Text",
            style=discord.TextStyle.paragraph,
            default=current_text,
            max_length=max_length,
            required=True,
        )
        self.add_item(self.text_input)

class APISettingModal(ui.Modal):
    def __init__(self, title: str):
        super().__init__(title=title)
        self.setting_input = ui.TextInput(
            label="Value",
            style=discord.TextStyle.short,
            required=True,
        )
        self.add_item(self.setting_input)

class UserIDModal(ui.Modal):
    def __init__(self, title: str):
        super().__init__(title=title)
        self.user_id_input = ui.TextInput(
            label="User ID",
            style=discord.TextStyle.short,
            placeholder="Enter user ID (e.g. 123456789012345678)",
            required=True,
        )
        self.add_item(self.user_id_input)

class ConfirmView(ui.View):
    def __init__(self, confirm_callback: Callable, cancel_callback: Callable = None):
        super().__init__(timeout=180)
        self.confirm_callback = confirm_callback
        self.cancel_callback = cancel_callback

    @ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        await self.confirm_callback(interaction)
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        if self.cancel_callback:
            await self.cancel_callback(interaction)
        else:
            await interaction.response.send_message("Operation canceled.", ephemeral=True)
        self.stop()

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
    def __init__(self, title: str, default_name: str = "", default_pattern: str = "", default_replace: str = ""):
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
            await interaction.message.edit(embed=embed, view=self)

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
                default_pattern=script.find_pattern,
                default_replace=script.replace_with
            )

            async def on_submit(modal_interaction):
                try:
                    re.compile(modal.pattern_input.value)
                except re.error as e:
                    await modal_interaction.response.send_message(
                        f"Invalid regex pattern: {e}", ephemeral=True
                    )
                    return

                script.name = modal.name_input.value
                script.find_pattern = modal.pattern_input.value
                script.replace_with = modal.replace_input.value
                
                self.regex_manager.save_scripts()
                
                await modal_interaction.response.send_message(
                    f"Updated regex script: '{script.name}'", ephemeral=True
                )
                
                embed = await self.generate_embed(interaction)
                await interaction.message.edit(embed=embed, view=self)

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
            await interaction.message.edit(embed=embed, view=self)

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
            
            async def confirm_callback(confirm_interaction):
                if self.regex_manager.remove_script(script_name):
                    await confirm_interaction.response.send_message(
                        f"Removed regex script: '{script_name}'", ephemeral=True
                    )
                    
                    embed = await self.generate_embed(interaction)
                    await interaction.message.edit(embed=embed, view=self)
                else:
                    await confirm_interaction.response.send_message(
                        f"Script '{script_name}' not found.", ephemeral=True
                    )

            confirm_view = ConfirmView(confirm_callback=confirm_callback)
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
                value=f"```{script.find_pattern}```", 
                inline=False
            )
            settings_embed.add_field(
                name="Replacement", 
                value=f"```{script.replace_with}```", 
                inline=False
            )
            
            if script.trim_out:
                settings_embed.add_field(
                    name="Trim Out", 
                    value=f"```{script.trim_out}```", 
                    inline=False
                )
                
            affects = []
            if script.affects_user_input:
                affects.append("User Input")
            if script.affects_ai_response:
                affects.append("AI Response")
            if script.affects_slash_commands:
                affects.append("Slash Commands")
            if script.affects_world_info:
                affects.append("World Info")
            if script.affects_reasoning:
                affects.append("Reasoning")
            
            settings_embed.add_field(
                name="Affects", 
                value=", ".join(affects) if affects else "None", 
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
