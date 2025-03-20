import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
import re
import os
import datetime
from typing import Dict, List
from openai import AsyncOpenAI
import asyncio

# Import helper modules
from helpers.regex_extension import *
from helpers.views import *
from helpers.openshape_helpers import setup_openshape_helpers
from helpers.cleanup_helpers import setup_cleanup
from helpers.config_manager import setup_config_manager

# Import memory manager
from vectordb.chroma_integration import setup_memory_system, MemoryCommand, SleepCommand

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openshape")


class OpenShape(commands.Bot):
    def __init__(self, config_path: str, *args, **kwargs):
        # Load configuration
        with open(config_path, "r", encoding="utf-8") as f:
            self.character_config = json.load(f)

        # Setup intents
        intents = discord.Intents.all()

        # Initialize the bot
        super().__init__(
            command_prefix=self.character_config.get("command_prefix", "!"),
            intents=intents,
            *args,
            **kwargs,
        )

        # Set basic config
        self.config_path = config_path
        self.owner_id = self.character_config.get("owner_id")
        self.character_name = self.character_config.get("character_name", "Assistant")

        # Conversation settings
        self.system_prompt = self.character_config.get("system_prompt", "")
        self.character_backstory = self.character_config.get("character_backstory", "")
        self.character_description = self.character_config.get("character_description", "")
        self.personality_catchphrases = self.character_config.get("personality_catchphrases")
        self.personality_age = self.character_config.get("personality_age")
        self.personality_likes = self.character_config.get("personality_likes")
        self.personality_dislikes = self.character_config.get("personality_dislikes")
        self.personality_goals = self.character_config.get("personality_goals")
        self.personality_traits = self.character_config.get("personality_traits")
        self.personality_physical_traits = self.character_config.get("personality_physical_traits")
        self.personality_tone = self.character_config.get("personality_tone")
        self.personality_history = self.character_config.get("personality_history")
        self.personality_conversational_goals = self.character_config.get("personality_conversational_goals")
        self.personality_conversational_examples = self.character_config.get("personality_conversational_examples")
        self.character_scenario = self.character_config.get("character_scenario", "")
        self.free_will = self.character_config.get("free_will", False)
        self.free_will_instruction = self.character_config.get("free_will_instruction", "")
        self.jailbreak = self.character_config.get("jailbreak", "")
        

        # API configuration for AI integration
        self.api_settings = self.character_config.get("api_settings", {})
        self.base_url = self.api_settings.get("base_url", "")
        self.api_key = self.api_settings.get("api_key", "")
        self.chat_model = self.api_settings.get("chat_model", "")
        self.tts_model = self.api_settings.get("tts_model", "")
        self.tts_voice = self.api_settings.get("tts_voice", "")

        # Initialize OpenAI client if API settings are provided
        self.ai_client = None
        if self.api_key and self.base_url:
            try:
                self.ai_client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    max_retries=2,
                    timeout=60,
                )
                logger.info("AI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize AI client: {e}")

        # File paths for storage
        self.data_dir = self.character_config.get("data_dir", "character_data")
        self.conversations_dir = os.path.join(self.data_dir, "conversations")
        self.memory_path = os.path.join(self.data_dir, "memory.json")
        self.lorebook_path = os.path.join(self.data_dir, "lorebook.json")
        self.audio_dir = os.path.join(self.data_dir, "audio")

        # Create directories if they don't exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.conversations_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

        # Response behavior settings
        self.add_character_name = self.character_config.get("add_character_name", True)
        self.always_reply_mentions = self.character_config.get(
            "always_reply_mentions", True
        )
        self.reply_to_name = self.character_config.get("reply_to_name", True)
        self.activated_channels = set(
            self.character_config.get("activated_channels", [])
        )
        self.use_tts = self.character_config.get("use_tts", False)

        # Moderation settings
        self.blacklisted_users = self.character_config.get("blacklisted_users", [])
        self.blacklisted_roles = self.character_config.get("blacklisted_roles", [])
        self.conversation_timeout = self.character_config.get("conversation_timeout", 30)  # Default 30 minutes

        # Initialize helper modules
        self.config_manager = setup_config_manager(self, config_path)
        self.helpers = setup_openshape_helpers(self)
        
        # Initialize ChromaMemoryManager
        shared_db_path = os.path.join(os.getcwd(), "shared_memory")
        self.memory_manager = setup_memory_system(self, shared_db_path)
        
        self.regex_manager = RegexManager(self)
        
        # Initialize storage for conversations
        self.channel_conversations = {}

    async def setup_hook(self):
        """Register slash commands when the bot is starting up"""
        # Basic commands
        self.tree.add_command(
            app_commands.Command(
                name="openshapes",
                description="Get help and learn how to use OpenShape bot",
                callback=self.openshape_help_command,
            )
        )
        
        
        self.tree.add_command(
            app_commands.Command(
                name="api_settings",
                description="Configure AI API settings",
                callback=self.api_settings_command,
            ),
        )

        self.tree.add_command(
            app_commands.Command(
                name="character_info",
                description="Show information about this character",
                callback=self.character_info_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="activate",
                description="Activate the bot to respond to all messages in the channel",
                callback=self.activate_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="deactivate",
                description="Deactivate the bot's automatic responses in the channel",
                callback=self.deactivate_command,
            )
        )

        # Memory and knowledge commands
        self.tree.add_command(
            app_commands.Command(
                name="memory",
                description="View or manage the character's memory",
                callback=self.memory_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="lorebook",
                description="Manage lorebook entries",
                callback=self.lorebook_command,
            )
        )

        # Settings command
        self.tree.add_command(
            app_commands.Command(
                name="settings",
                description="Manage character settings",
                callback=self.settings_command,
            )
        )
        self.tree.add_command(
            app_commands.Command(
                name="edit_personality_traits",
                description="Edit specific personality traits for the character",
                callback=self.edit_personality_traits_command,
            ),
        )
        
        self.tree.add_command(
            app_commands.Command(
                name="edit_backstory",
                description="Edit the character's history and background",
                callback=self.edit_backstory_command,
            ),
        )
        
        self.tree.add_command(
            app_commands.Command(
                name="edit_preferences",
                description="Edit what the character likes and dislikes",
                callback=self.edit_preferences_command,
            ),
        )
        # 
        self.tree.add_command(
            app_commands.Command(
                name="sleep",
                description="Generate a long term memory.",
                callback=self.sleep_command,
            ),
        )
        # Regex command
        self.tree.add_command(
            app_commands.Command(
                name="regex",
                description="Manage RegEx pattern scripts for text manipulation",
                callback=self.regex_command,
            )
        )
        # Configuration commands (owner only)
        for guild_id in self.character_config.get("allowed_guilds", []):
            guild = discord.Object(id=guild_id)

            self.tree.add_command(
                app_commands.Command(
                    name="edit_prompt",
                    description="Edit the character's system prompt",
                    callback=self.edit_prompt_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="edit_description",
                    description="Edit the character's description",
                    callback=self.edit_description_command,
                ),
                guild=guild,
            )


            self.tree.add_command(
                app_commands.Command(
                    name="edit_scenario",
                    description="Edit the character's scenario",
                    callback=self.edit_scenario_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="blacklist",
                    description="Add or remove a user from the blacklist",
                    callback=self.blacklist_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="save",
                    description="Save all current settings and data",
                    callback=self.save_command,
                ),
                guild=guild,
            )

    async def character_info_command(self, interaction: discord.Interaction):
        """Public command to show character information"""
        # Create a list to hold multiple embeds if needed
        class PaginationView(discord.ui.View):
            def __init__(self, embeds):
                super().__init__(timeout=120)
                self.embeds = embeds
                self.current_page = 0
                self.total_pages = len(embeds)
                # Add page count to each embed
                for i, embed in enumerate(self.embeds):
                    embed.set_footer(text=f"Page {i+1}/{self.total_pages}")
            
            @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary, disabled=True)
            async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page = max(0, self.current_page - 1)
                # Enable/disable buttons based on current page
                self.previous_button.disabled = self.current_page == 0
                self.next_button.disabled = self.current_page == self.total_pages - 1
                await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

            @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page = min(self.total_pages - 1, self.current_page + 1)
                # Enable/disable buttons based on current page
                self.previous_button.disabled = self.current_page == 0
                self.next_button.disabled = self.current_page == self.total_pages - 1
                await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
                
        embeds = []
        
        # First embed with basic info
        embed = discord.Embed(title=f"{self.character_name} Info", color=0x3498DB)
        current_size = len(embed.title)
        
        # Track available fields to show
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
        
        # Add fields to embeds, creating new embeds when needed
        for field in fields:
            field_size = len(field["name"]) + len(field["value"])
            
            # Check if adding this field would exceed the embed size limit (5800 to be safe)
            if current_size + field_size > 5800:
                # Add current embed to the list and create a new one
                embeds.append(embed)
                embed = discord.Embed(title=f"{self.character_name} Info (Continued)", color=0x3498DB)
                current_size = len(embed.title)
            
            # Add field to the current embed
            embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])
            current_size += field_size
        
        # Add the final embed to the list
        embeds.append(embed)
        
        # If only one embed, send without pagination
        if len(embeds) == 1:
            await interaction.response.send_message(embed=embeds[0])
        else:
            # Create pagination view
            view = PaginationView(embeds)
            await interaction.response.send_message(embed=embeds[0], view=view)

    async def activate_command(self, interaction: discord.Interaction):
        """Activate the bot in the current channel"""
        self.activated_channels.add(interaction.channel_id)
        self.config_manager.save_config()
        await interaction.response.send_message(
            f"{self.character_name} will now respond to all messages in this channel."
        )

    async def deactivate_command(self, interaction: discord.Interaction):
        """Deactivate the bot in the current channel"""
        if interaction.channel_id in self.activated_channels:
            self.activated_channels.remove(interaction.channel_id)
            self.config_manager.save_config()
        await interaction.response.send_message(
            f"{self.character_name} will now only respond when mentioned or called by name."
        )

    async def edit_personality_traits_command(self, interaction: discord.Interaction):
        """Edit the character's specific personality traits"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create dropdown for selecting which trait to edit
        options = [
            discord.SelectOption(label="Catchphrases", value="catchphrases"),
            discord.SelectOption(label="Age", value="age"),
            discord.SelectOption(label="Traits", value="traits"),
            discord.SelectOption(label="Physical Traits", value="physical"),
            discord.SelectOption(label="Tone", value="tone"),
            discord.SelectOption(label="Conversational Style", value="style"),
        ]

        select = discord.ui.Select(placeholder="Select trait to edit", options=options)

        async def select_callback(select_interaction):
            trait = select.values[0]
            
            current_values = {
                "catchphrases": self.personality_catchphrases,
                "age": self.personality_age,
                "traits": self.personality_traits,
                "physical": self.personality_physical_traits,
                "tone": self.personality_tone,
                "style": self.personality_conversational_examples
            }
            
            # Create modal for editing
            modal = TextEditModal(
                title=f"Edit {trait.title()}", 
                current_text=current_values[trait] or ""
            )

            async def on_submit(modal_interaction):
                # Update the appropriate field
                if trait == "catchphrases":
                    self.personality_catchphrases = modal.text_input.value
                elif trait == "age":
                    self.personality_age = modal.text_input.value
                elif trait == "traits":
                    self.personality_traits = modal.text_input.value
                elif trait == "physical":
                    self.personality_physical_traits = modal.text_input.value
                elif trait == "tone":
                    self.personality_tone = modal.text_input.value
                elif trait == "style":
                    self.personality_conversational_examples = modal.text_input.value
                    
                self.config_manager.save_config()
                await modal_interaction.response.send_message(
                    f"Character {trait} updated!", ephemeral=True
                )

            modal.on_submit = on_submit
            await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            "Select a personality trait to edit:", view=view, ephemeral=True
        )

    async def edit_backstory_command(self, interaction: discord.Interaction):
        """Edit the character's history"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
        modal = TextEditModal(
            title="Edit Character History", 
            current_text=self.personality_history or ""
        )

        async def on_submit(modal_interaction):
            self.personality_history = modal.text_input.value
            self.config_manager.save_config()
            await modal_interaction.response.send_message(
                "Character history updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    async def edit_preferences_command(self, interaction: discord.Interaction):
        """Edit what the character likes and dislikes"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create dropdown to select likes or dislikes
        options = [
            discord.SelectOption(label="Likes", value="likes"),
            discord.SelectOption(label="Dislikes", value="dislikes"),
            discord.SelectOption(label="Goals", value="goals"),
        ]

        select = discord.ui.Select(placeholder="Select preference to edit", options=options)

        async def select_callback(select_interaction):
            pref = select.values[0]
            
            current_values = {
                "likes": self.personality_likes,
                "dislikes": self.personality_dislikes,
                "goals": self.personality_goals
            }
            
            # Create modal for editing
            modal = TextEditModal(
                title=f"Edit {pref.title()}", 
                current_text=current_values[pref] or ""
            )

            async def on_submit(modal_interaction):
                # Update the appropriate field
                if pref == "likes":
                    self.personality_likes = modal.text_input.value
                elif pref == "dislikes":
                    self.personality_dislikes = modal.text_input.value
                elif pref == "goals":
                    self.personality_goals = modal.text_input.value
                    
                self.config_manager.save_config()
                await modal_interaction.response.send_message(
                    f"Character {pref} updated!", ephemeral=True
                )

            modal.on_submit = on_submit
            await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            "Select preferences to edit:", view=view, ephemeral=True
        )
        
    async def sleep_command(self, interaction: discord.Interaction):
        """Process recent messages to extract and store memories before going to sleep"""
        await SleepCommand.execute(self, interaction)
    
    async def memory_command(self, interaction: discord.Interaction):
        """View or manage memories with source attribution"""
        await MemoryCommand.execute(self, interaction)

    async def api_settings_command(self, interaction: discord.Interaction):
        """Configure AI API settings"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create a selection menu for API settings actions
        options = [
            discord.SelectOption(label="View Current Settings", value="view"),
            discord.SelectOption(label="Set Base URL", value="base_url"),
            discord.SelectOption(label="Set API Key", value="api_key"),
            discord.SelectOption(label="Set Chat Model", value="chat_model"),
            discord.SelectOption(label="Set TTS Model", value="tts_model"),
            discord.SelectOption(label="Set TTS Voice", value="tts_voice"),
            discord.SelectOption(label="Toggle TTS", value="toggle_tts"),
            discord.SelectOption(label="Test Connection", value="test"),
        ]

        select = discord.ui.Select(placeholder="Select API Setting", options=options)

        async def select_callback(select_interaction):
            action = select.values[0]

            if action == "view":
                # Hide API key for security
                masked_key = "••••••" + self.api_key[-4:] if self.api_key else "Not set"
                settings_info = f"**API Settings:**\n"
                settings_info += f"- Base URL: {self.base_url or 'Not set'}\n"
                settings_info += f"- API Key: {masked_key}\n"
                settings_info += f"- Chat Model: {self.chat_model or 'Not set'}\n"
                settings_info += f"- TTS Model: {self.tts_model or 'Not set'}\n"
                settings_info += f"- TTS Voice: {self.tts_voice or 'Not set'}\n"
                settings_info += f"- TTS Enabled: {'Yes' if self.use_tts else 'No'}"

                await select_interaction.response.send_message(
                    settings_info, ephemeral=True
                )

            elif action == "toggle_tts":
                self.use_tts = not self.use_tts
                self.config_manager.update_field("use_tts", self.use_tts)
                await select_interaction.response.send_message(
                    f"TTS has been {'enabled' if self.use_tts else 'disabled'}",
                    ephemeral=True,
                )

            elif action == "test":
                if (
                    not self.ai_client
                    or not self.api_key
                    or not self.base_url
                    or not self.chat_model
                ):
                    await select_interaction.response.send_message(
                        "Cannot test API connection: Missing required API settings",
                        ephemeral=True,
                    )
                    return

                await select_interaction.response.defer(ephemeral=True)

                try:
                    # Test chat completion
                    completion = await self.api_manager.call_chat_api(
                        "Hello, this is a test message."
                    )

                    if completion:
                        await select_interaction.followup.send(
                            f"API connection successful!\nTest response: {completion[:100]}...",
                            ephemeral=True,
                        )
                    else:
                        await select_interaction.followup.send(
                            "API test failed: No response received", ephemeral=True
                        )
                except Exception as e:
                    await select_interaction.followup.send(
                        f"API test failed: {str(e)}", ephemeral=True
                    )

            else:
                # Create modal for setting value
                modal = APISettingModal(title=f"Set {action.replace('_', ' ').title()}")

                async def on_submit(modal_interaction):
                    value = modal.setting_input.value

                    # Update the appropriate setting
                    if action == "base_url":
                        self.base_url = value
                        self.api_settings["base_url"] = value
                    elif action == "api_key":
                        self.api_key = value
                        self.api_settings["api_key"] = value
                    elif action == "chat_model":
                        self.chat_model = value
                        self.api_settings["chat_model"] = value
                    elif action == "tts_model":
                        self.tts_model = value
                        self.api_settings["tts_model"] = value
                    elif action == "tts_voice":
                        self.tts_voice = value
                        self.api_settings["tts_voice"] = value

                    # Update config and reinitialize client
                    self.config_manager.update_field("api_settings", self.api_settings)

                    # Reinitialize OpenAI client if base URL and API key are set
                    if self.api_key and self.base_url:
                        try:
                            self.ai_client = AsyncOpenAI(
                                api_key=self.api_key,
                                base_url=self.base_url,
                                max_retries=2,
                                timeout=60,
                            )
                            await modal_interaction.response.send_message(
                                f"{action.replace('_', ' ').title()} updated and client reinitialized!",
                                ephemeral=True,
                            )
                        except Exception as e:
                            await modal_interaction.response.send_message(
                                f"{action.replace('_', ' ').title()} updated but client initialization failed: {e}",
                                ephemeral=True,
                            )
                    else:
                        await modal_interaction.response.send_message(
                            f"{action.replace('_', ' ').title()} updated!",
                            ephemeral=True,
                        )

                modal.on_submit = on_submit
                await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            "Configure API Settings:", view=view, ephemeral=True
        )

    async def lorebook_command(self, interaction: discord.Interaction):
        """Manage lorebook entries"""
        # Check if user is owner for management
        if interaction.user.id != self.owner_id:
            if not self.lorebook_entries:
                await interaction.response.send_message(
                    "No lorebook entries exist yet."
                )
                return

            # Show lorebook entries to non-owners
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

        # Create a view for lorebook management
        view = LorebookManagementView(self)
        lore_display = self.lorebook_manager.format_entries_for_display()
        await interaction.response.send_message(lore_display, view=view)

    async def settings_command(self, interaction: discord.Interaction):
        """Display and modify bot settings"""
        # Only allow the owner to change settings
        if interaction.user.id != self.owner_id:
            settings_display = f"**{self.character_name} Settings:**\n"
            settings_display += f"- Add name to responses: {'Enabled' if self.add_character_name else 'Disabled'}\n"
            settings_display += f"- Reply to mentions: {'Enabled' if self.always_reply_mentions else 'Disabled'}\n"
            settings_display += f"- Reply when name is called: {'Enabled' if self.reply_to_name else 'Disabled'}\n"

            await interaction.response.send_message(settings_display)
            return

        # Create a view with settings toggles
        view = SettingsView(self)

        settings_display = f"**{self.character_name} Settings:**\n"
        settings_display += f"- Add name to responses: {'Enabled' if self.add_character_name else 'Disabled'}\n"
        settings_display += f"- Reply to mentions: {'Enabled' if self.always_reply_mentions else 'Disabled'}\n"
        settings_display += f"- Reply when name is called: {'Enabled' if self.reply_to_name else 'Disabled'}\n"

        await interaction.response.send_message(settings_display, view=view)

    async def edit_prompt_command(self, interaction: discord.Interaction):
        """Edit the character's system prompt"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
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

    async def edit_backstory_commad(self, interaction: discord.Interaction):
        """Edit the character's backstory"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
        modal = TextEditModal(
            title="Edit Backstory", current_text=self.character_backstory
        )

        async def on_submit(modal_interaction):
            self.character_backstory = modal.text_input.value
            self.config_manager.save_config()
            await modal_interaction.response.send_message(
                "Character backstory updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def edit_description_command(self, interaction: discord.Interaction):
        """Edit the character's description"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
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
        """Edit the character's scenario"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
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

    async def edit_presets_command(self, interaction: discord.Interaction):
        """Edit the character's presets"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
        modal = TextEditModal(
            title="Edit Presets", current_text=self.jailbreak
        )

        async def on_submit(modal_interaction):
            self.jailbreak = modal.text_input.value
            self.config_manager.save_config()
            await modal_interaction.response.send_message(
                "Character presets updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def blacklist_command(self, interaction: discord.Interaction):
        """Add or remove a user from blacklist"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create a selection menu for blacklist actions
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
                # Create modal for adding user ID
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

                # Create modal for removing user ID
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
        """Save all data and configuration"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Save everything
        self.config_manager.save_config()
        self.memory_manager._save_memory()
        self.lorebook_manager._save_lorebook()

        await interaction.response.send_message(
            "All data and settings saved!", ephemeral=True
        )

    # Method to handle regex command
    async def regex_command(self, interaction: discord.Interaction):
        """Manage RegEx scripts for text manipulation patterns"""
        # Only allow the bot owner to access this command
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can manage RegEx scripts.", ephemeral=True
            )
            return
            
        # Create view and initial embed
        view = RegexManagementView(self.regex_manager)
        embed = await view.generate_embed(interaction)
        
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )
        
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        await self.tree.sync()
        self.cleanup = setup_cleanup(self)
        logger.info(f"Character name: {self.character_name}")

    async def on_message(self, message: discord.Message):
        """Process incoming messages and respond if appropriate"""
        # Ignore own messages
        if message.author == self.user:
            return

        # Process commands with prefix
        await self.process_commands(message)

        # Check if user is blacklisted
        if message.author.id in self.blacklisted_users:
            return

        # Check if we should respond
        should_respond = False

        # Check if the channel is activated for responding to all messages
        if message.channel.id in self.activated_channels:
            should_respond = True

        # Respond to direct mentions
        elif self.always_reply_mentions and self.user in message.mentions:
            should_respond = True

        # Respond when name is called
        elif (
            self.reply_to_name
            and self.character_name.lower() in message.content.lower()
        ):
            should_respond = True

        # Check for OOC command prefix (out of character)
        is_ooc = message.content.startswith("//") or message.content.startswith("/ooc")
        if is_ooc and message.author.id == self.owner_id:
            await self._handle_ooc_command(message)
            return
        
        # Apply RegEx to message content if needed
        processed_content = message.content
        if hasattr(self, 'regex_manager'):
            # Define common macros
            macros = {
                "user": message.author.display_name,
                "char": self.character_name,
                "server": message.guild.name if message.guild else "DM",
                "channel": message.channel.name if hasattr(message.channel, 'name') else "DM"
            }
            
            processed_content = self.regex_manager.process_text(
                processed_content, 
                "user_input", 
                macros=macros
            )

        if should_respond:
            async with message.channel.typing():
                guild_id = str(message.guild.id) if message.guild else "global"
                
                # Remove mentions from the message
                clean_content = re.sub(r"<@!?(\d+)>", "", message.content).strip()

                # Get conversation history for this channel (limited to 8 messages)
                channel_history = self.message_processor.get_channel_conversation(message.channel.id)
                
                # Add the new message to history
                channel_history.append(
                    {
                        "role": "user",
                        "name": message.author.display_name,
                        "content": clean_content,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "discord_id": str(message.author.id),
                    }
                )
             
                # Ensure we maintain the 8 message limit
                if len(channel_history) > 8:
                    channel_history = channel_history[-8:]

                # Get relevant lorebook entries
                relevant_lore = self.lorebook_manager.get_relevant_entries(clean_content)
                
                # Get relevant memories using our new search function
                relevant_memories = self.memory_manager.search_memory(clean_content, guild_id)
                
                # Combine lore and memories into single relevant_info list
                relevant_info = []
                if relevant_lore:
                    relevant_info.extend(relevant_lore)
                if relevant_memories:
                    relevant_info.extend(relevant_memories)

                # Generate a response based on persona, history and relevant information
                response = await self.api_manager.generate_response(
                    message.author.display_name,
                    clean_content,
                    channel_history,
                    relevant_info,
                )
                
                # Process AI response with regex if needed
                if hasattr(self, 'regex_manager'):
                    response = self.regex_manager.process_text(
                        response, 
                        "ai_response", 
                        macros=macros
                    )

                # Add response to history
                channel_history.append(
                    {
                        "role": "assistant",
                        "name": self.character_name,
                        "content": response,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "discord_id": str(self.user.id),
                    }
                )
                
                # Again, ensure we maintain the 8 message limit
                if len(channel_history) > 8:
                    channel_history = channel_history[-8:]

                # Update memory if there's something important to remember
                await self.memory_manager.update_memory_from_conversation(
                    message.author.display_name, clean_content, response, guild_id
                )

                # Save conversation periodically
                # Note: Changed to save every time since we're limiting to 8 messages anyway
                self.message_processor.save_conversation(message.channel.id, channel_history)

                # Format response with name if enabled
                formatted_response = (
                    f"**{self.character_name}**: {response}"
                    if self.add_character_name
                    else response
                )
                
                # Generate and send TTS if enabled AND user is in a voice channel
                if self.use_tts and message.guild and message.author.voice and message.author.voice.channel:
                    try:
                        # Generate TTS directly without saving to a permanent file
                        temp_audio_file = await self.tts_handler.generate_temp_tts(response)
                        if temp_audio_file:
                            voice_channel = message.author.voice.channel

                            # Connect to voice channel
                            voice_client = message.guild.voice_client
                            if voice_client:
                                if voice_client.channel != voice_channel:
                                    await voice_client.move_to(voice_channel)
                            else:
                                voice_client = await voice_channel.connect()

                            # Play audio and set up cleanup
                            def after_playing(error):
                                # Delete the temporary file after it's been played
                                try:
                                    os.remove(temp_audio_file)
                                    logger.info(f"Deleted temporary TTS file: {temp_audio_file}")
                                except Exception as e:
                                    logger.error(f"Error deleting temporary TTS file: {e}")
                                
                                # Disconnect from voice channel
                                asyncio.run_coroutine_threadsafe(
                                    self.tts_handler.disconnect_after_audio(voice_client),
                                    self.loop,
                                )

                            voice_client.play(
                                discord.FFmpegPCMAudio(temp_audio_file),
                                after=after_playing,
                            )
                    except Exception as e:
                        logger.error(f"Error playing TTS audio: {e}")
                else:
                    # Send the response in text form
                    sent_message, message_group = await self.message_processor.send_long_message(
                        message.channel,
                        formatted_response,
                        reference=message,
                        reply=True
                    )

                    # Add reactions only to the primary message
                    await sent_message.add_reaction("🗑️")
                    await sent_message.add_reaction("♻️")

                    # Store context for regeneration
                    context = {
                        "user_name": message.author.display_name,
                        "user_message": clean_content,
                        "channel_history": channel_history[:-1],  # Don't include the bot's response
                        "relevant_info": relevant_info,  # Store combined lore and memories
                        "original_message": message.id,  # Store original message ID for reply
                        "user_discord_id": str(message.author.id),
                    }
                    
                    # Save the context needed for regeneration - save it for all message parts
                    primary_id = message_group["primary_id"]
                    if primary_id:
                        self.message_processor.save_message_context(primary_id, context)
    
    
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle reactions to messages with improved recycling emoji behavior"""
        # Ignore bot's own reaction adds
        if user.id == self.user.id:
            return
            
        # Get message ID to check if it's part of a multipart message
        message_id = reaction.message.id
        message_group = None
        
        # Check if this message is part of a multipart message group
        if self.message_processor.is_multipart_message(message_id):
            message_group = self.message_processor.get_message_group(message_id)
        
        # If the reaction is the trash emoji on the bot's message
        if (
            reaction.emoji == "🗑️"
            and reaction.message.author == self.user
            and (
                user.id == self.owner_id
                or (
                    hasattr(reaction.message, "reference")
                    and reaction.message.reference
                    and reaction.message.reference.resolved
                    and user.id == reaction.message.reference.resolved.author.id
                )
            )
        ):
            # If it's a multipart message, delete all parts
            if message_group and message_group["is_multipart"]:
                for msg_id in message_group["message_ids"]:
                    try:
                        # Try to fetch and delete each message
                        msg = await reaction.message.channel.fetch_message(msg_id)
                        await msg.delete()
                    except (discord.NotFound, discord.HTTPException):
                        # Message may already be deleted or not found
                        continue
            else:
                # Single message, just delete it
                await reaction.message.delete()
            
        # If the reaction is the recycle emoji (♻️) on the bot's message
        elif (
            reaction.emoji == "♻️"
            and reaction.message.author == self.user
        ):
            # Only allow if:
            # 1. User is the original message author (the one the bot replied to)
            # 2. Message doesn't have a "regenerated" flag
            is_original_author = (
                hasattr(reaction.message, "reference")
                and reaction.message.reference
                and reaction.message.reference.resolved
                and user.id == reaction.message.reference.resolved.author.id
            )
            
            # Check for regeneration flag (added as a reaction by the bot)
            already_regenerated = any(r.emoji == "🔄" and r.me for r in reaction.message.reactions)
            
            if is_original_author and not already_regenerated:
                # Determine which message ID to use for context lookup
                context_message_id = message_id
                if message_group and message_group["primary_id"]:
                    context_message_id = message_group["primary_id"]
                    
                # Check if we have the context stored for regeneration
                context = self.message_processor.get_message_context(context_message_id)
                
                if context:
                    # Show typing indicator
                    async with reaction.message.channel.typing():
                        # Get a new response with the saved context
                        new_response = await self.api_manager.generate_response(
                            context["user_name"],
                            context["user_message"],
                            context["channel_history"],
                            context["relevant_info"]  # Use the saved relevant_info (lore + memories)
                        )
                        
                        # Format response with name if enabled
                        formatted_response = (
                            f"**{self.character_name}**: {new_response}"
                            if self.add_character_name
                            else new_response
                        )
                        
                        # Handle multipart messages differently
                        if message_group and message_group["is_multipart"]:
                            # Delete all the old messages first
                            for msg_id in message_group["message_ids"]:
                                try:
                                    msg = await reaction.message.channel.fetch_message(msg_id)
                                    await msg.delete()
                                except (discord.NotFound, discord.HTTPException):
                                    continue
                            
                            # Get the original message
                            try:
                                original_message = await reaction.message.channel.fetch_message(context["original_message"])
                                
                                # Send the new response as a new multipart message
                                primary_message, new_message_group = await self.message_processor.send_long_message(
                                    reaction.message.channel, 
                                    formatted_response,
                                    reference=original_message
                                )
                                
                                # Add reaction to just the primary message
                                await primary_message.add_reaction("🗑️")
                                await primary_message.add_reaction("🔄")  # Mark as already regenerated
                                
                                # Update the context for the new primary message
                                self.message_processor.save_message_context(primary_message.id, context)
                                
                            except (discord.NotFound, discord.HTTPException):
                                # If original message is gone, just send as new message
                                primary_message, new_message_group = await self.message_processor.send_long_message(
                                    reaction.message.channel, 
                                    formatted_response
                                )
                                await primary_message.add_reaction("🗑️")
                                await primary_message.add_reaction("🔄")
                        else:
                            # Single message - try to edit, fall back to delete and resend
                            try:
                                # First attempt to edit the existing message
                                await reaction.message.edit(content=formatted_response)
                                edited_message = reaction.message
                                
                                # Add a "regenerated" flag reaction to prevent further regeneration
                                await edited_message.add_reaction("🔄")
                                
                            except discord.HTTPException:
                                # If editing fails (e.g., too old message), delete and send new one
                                await reaction.message.delete()
                                
                                # Get the original message
                                try:
                                    original_message = await reaction.message.channel.fetch_message(context["original_message"])
                                    
                                    # Send the new response, potentially splitting if too long
                                    primary_message, new_message_group = await self.message_processor.send_long_message(
                                        reaction.message.channel, 
                                        formatted_response,
                                        reference=original_message
                                    )
                                    
                                    # Add reactions to new message
                                    await primary_message.add_reaction("🗑️")
                                    await primary_message.add_reaction("🔄")  # Mark as already regenerated
                                    
                                    # Update the context for the new message
                                    self.message_processor.save_message_context(primary_message.id, context)
                                    
                                except (discord.NotFound, discord.HTTPException):
                                    # Couldn't find original message, just send as a new message
                                    primary_message, new_message_group = await self.message_processor.send_long_message(
                                        reaction.message.channel, 
                                        formatted_response
                                    )
                                    await primary_message.add_reaction("🗑️")
                        
                        # Update conversation history with the new response
                        channel_history = self.message_processor.get_channel_conversation(reaction.message.channel.id)
                        
                        # Replace the last bot response or add this one
                        if channel_history and channel_history[-1]["role"] == "assistant":
                            channel_history[-1] = {
                                "role": "assistant",
                                "name": self.character_name,
                                "content": new_response,
                                "timestamp": datetime.datetime.now().isoformat(),
                            }
                        else:
                            channel_history.append({
                                "role": "assistant",
                                "name": self.character_name,
                                "content": new_response,
                                "timestamp": datetime.datetime.now().isoformat(),
                            })
                        
                        # Save the updated conversation
                        self.message_processor.save_conversation(reaction.message.channel.id, channel_history)
                        
                        # Check if we need to update memory from the regenerated response
                        await self.memory_manager.update_memory_from_conversation(
                            context["user_name"], context["user_message"], new_response
                        )
    
    async def _handle_ooc_command(self, message: discord.Message):
        """Handle out-of-character commands from the owner"""
        clean_content = message.content.replace("//", "").replace("/ooc", "").strip()
        parts = clean_content.split(" ", 1)
        command = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        guild_id = str(message.guild.id) if message.guild else "global"
    
        if command == "regex":
            if not args:
                # Show help for regex commands
                help_text = "**RegEx Commands:**\n"
                help_text += "- `//regex list` - List all regex scripts\n"
                help_text += "- `//regex test <script_name> <text>` - Test a regex script on text\n"
                help_text += "- `//regex toggle <script_name>` - Enable/disable a script\n"
                help_text += "- `//regex info <script_name>` - Show detailed info about a script\n"
                await message.reply(help_text)
                return
                
            subparts = args.split(" ", 1)
            subcommand = subparts[0].lower() if subparts else ""
            subargs = subparts[1] if len(subparts) > 1 else ""
            
            if subcommand == "list":
                # List all regex scripts
                scripts = self.regex_manager.scripts
                
                embed = discord.Embed(title="RegEx Scripts")
                
                if scripts:
                    scripts_text = ""
                    for i, script in enumerate(scripts, 1):
                        status = "✅" if not script.disabled else "❌"
                        scripts_text += f"{i}. {status} **{script.name}**\n"
                    embed.add_field(name="Scripts", value=scripts_text, inline=False)
                else:
                    embed.add_field(name="Scripts", value="No scripts", inline=False)
                    
                await message.reply(embed=embed)
                
            elif subcommand == "test" and subargs:
                # Test a regex script on text
                test_parts = subargs.split(" ", 1)
                if len(test_parts) != 2:
                    await message.reply("Format: //regex test <script_name> <text>")
                    return
                    
                script_name, test_text = test_parts
                
                # Find the script
                script = self.regex_manager.get_script(script_name, self.character_name)
                
                if not script:
                    await message.reply(f"Script '{script_name}' not found.")
                    return
                    
                # Test the script
                result = script.apply(test_text)
                
                embed = discord.Embed(title=f"RegEx Test: {script.name}")
                embed.add_field(name="Input", value=test_text[:1024], inline=False)
                embed.add_field(name="Output", value=result[:1024], inline=False)
                
                if test_text == result:
                    embed.set_footer(text="⚠️ No changes were made")
                    embed.color = discord.Color.yellow()
                else:
                    embed.set_footer(text="✅ Text was transformed")
                    embed.color = discord.Color.green()
                    
                await message.reply(embed=embed)
                
            elif subcommand == "toggle" and subargs:
                # Enable/disable a script
                script_name = subargs.strip()
                script = self.regex_manager.get_script(script_name)
                
                if not script:
                    await message.reply(f"Script '{script_name}' not found.")
                    return
                    
                script.disabled = not script.disabled
                
                # Save the changes
                self.regex_manager.save_scripts()
                    
                status = "disabled" if script.disabled else "enabled"
                await message.reply(f"Script '{script_name}' is now {status}.")
                
            elif subcommand == "info" and subargs:
                # Show detailed info about a script
                script_name = subargs.strip()
                script = self.regex_manager.get_script(script_name)
                
                if not script:
                    await message.reply(f"Script '{script_name}' not found.")
                    return
                    
                embed = discord.Embed(title=f"RegEx Script: {script.name}")
                embed.add_field(name="Pattern", value=f"`{script.find_pattern}`", inline=False)
                embed.add_field(name="Replace With", value=f"`{script.replace_with}`", inline=False)
                
                if script.trim_out:
                    embed.add_field(name="Trim Out", value=f"`{script.trim_out}`", inline=False)
                    
                affects = []
                if script.affects_user_input: affects.append("User Input")
                if script.affects_ai_response: affects.append("AI Response")
                if script.affects_slash_commands: affects.append("Slash Commands")
                if script.affects_world_info: affects.append("World Info")
                if script.affects_reasoning: affects.append("Reasoning")
                
                embed.add_field(name="Affects", value=", ".join(affects) if affects else "None", inline=False)
                embed.add_field(name="Status", value="Enabled" if not script.disabled else "Disabled", inline=False)
                
                await message.reply(embed=embed)
            else:
                await message.reply(f"Unknown regex subcommand: {subcommand}")
                
        elif command == "memory" or command == "wack":
            if args.lower() == "show":
                memory_display = self.memory_manager.format_memories_for_display(guild_id)
            
                # Split long memory display into chunks of 1900 characters (leaving some room for formatting)
                if len(memory_display) > 1900:
                    chunks = []
                    current_chunk = "**Character Memories:**\n"
                    
                    # Split by memory entries (assuming they're separated by newlines)
                    memory_entries = memory_display.split("\n")
                    
                    for entry in memory_entries:
                        # Skip empty lines
                        if not entry.strip():
                            continue
                            
                        # If adding this entry would exceed the limit, start a new chunk
                        if len(current_chunk) + len(entry) + 1 > 1900:
                            chunks.append(current_chunk)
                            current_chunk = f"**Character Memories (continued):**\n{entry}\n"
                        else:
                            current_chunk += f"{entry}\n"
                    
                    # Add the last chunk if it has content
                    if current_chunk.strip() != "**Character Memories (continued):**":
                        chunks.append(current_chunk)
                    
                    # Send each chunk as a separate message
                    for i, chunk in enumerate(chunks):
                        await message.reply(chunk)
                else:
                    # Send as a single message if it's short enough
                    await message.reply(memory_display)
            elif args.lower().startswith("search ") and len(parts) > 2:
                # New command to search memories based on keywords
                search_term = parts[2]
                relevant_memories = self.memory_manager.search_memory(search_term, guild_id)
                
                if relevant_memories:
                    # Combine all memories into one display string
                    memory_display = f"**Memories matching '{search_term}':**\n"
                    for memory in relevant_memories:
                        memory_display += f"{memory}\n"
                    
                    # Split long memory display into chunks of 1900 characters
                    if len(memory_display) > 1900:
                        chunks = []
                        current_chunk = memory_display[:memory_display.find('\n')+1]  # Include header in first chunk
                        
                        # Split by memory entries (assuming they're separated by newlines)
                        memory_entries = memory_display[memory_display.find('\n')+1:].split("\n")
                        
                        for entry in memory_entries:
                            # Skip empty lines
                            if not entry.strip():
                                continue
                                
                            # If adding this entry would exceed the limit, start a new chunk
                            if len(current_chunk) + len(entry) + 1 > 1900:
                                chunks.append(current_chunk)
                                current_chunk = f"**Memories matching '{search_term}' (continued):**\n{entry}\n"
                            else:
                                current_chunk += f"{entry}\n"
                        
                        # Add the last chunk if it has content
                        if current_chunk.strip() != f"**Memories matching '{search_term}' (continued):**":
                            chunks.append(current_chunk)
                        
                        # Send each chunk as a separate message
                        for chunk in chunks:
                            await message.reply(chunk)
                    else:
                        # Send as a single message if it's short enough
                        await message.reply(memory_display)
            elif args.lower().startswith("add "):
                # Add memory manually
                mem_parts = args[4:].split(":", 1)
                if len(mem_parts) == 2:
                    topic, details = mem_parts
                    # Store with the command issuer as source
                    self.memory_manager.add_memory(topic.strip(), details.strip(), message.author.display_name, guild_id)
                    await message.reply(f"Added memory: {topic.strip()} (from {message.author.display_name})")
                else:
                    await message.reply(
                        "Invalid format. Use: //memory add Topic: Details"
                    )
            elif args.lower().startswith("remove "):
                # Remove memory
                topic = args[7:].strip()
                if self.memory_manager.remove_memory(topic, guild_id):
                    await message.reply(f"Removed memory: {topic}")
                else:
                    await message.reply(f"Memory topic '{topic}' not found.")
            elif args.lower() == "clear" or command == "wack":
                self.memory_manager.clear_memories(guild_id)
                await message.reply("All memories cleared.")
        elif command == "lore":
            subparts = args.split(" ", 1)
            subcommand = subparts[0].lower() if subparts else ""
            subargs = subparts[1] if len(subparts) > 1 else ""

            if subcommand == "add" and subargs:
                # Add lorebook entry manually
                lore_parts = subargs.split(":", 1)
                if len(lore_parts) == 2:
                    keyword, content = lore_parts
                    self.lorebook_manager.add_entry(keyword.strip(), content.strip())
                    await message.reply(
                        f"Added lorebook entry for keyword: {keyword.strip()}"
                    )
                else:
                    await message.reply(
                        "Invalid format. Use: //lore add Keyword: Content"
                    )
            elif subcommand == "list":
                lore_display = self.lorebook_manager.format_entries_for_display()
                await message.reply(lore_display)
            elif subcommand == "remove" and subargs:
                try:
                    index = int(subargs) - 1
                    if self.lorebook_manager.remove_entry(index):
                        await message.reply(
                            f"Removed lorebook entry #{index+1}"
                        )
                    else:
                        await message.reply("Invalid entry number.")
                except ValueError:
                    await message.reply("Please provide a valid entry number.")
            elif subcommand == "clear":
                self.lorebook_manager.clear_entries()
                await message.reply("All lorebook entries cleared.")

        elif command == "activate":
            self.activated_channels.add(message.channel.id)
            self.config_manager.save_config()
            await message.reply(
                f"{self.character_name} will now respond to all messages in this channel."
            )

        elif command == "deactivate":
            if message.channel.id in self.activated_channels:
                self.activated_channels.remove(message.channel.id)
                self.config_manager.save_config()
            await message.reply(
                f"{self.character_name} will now only respond when mentioned or called by name."
            )

        elif command == "persona":
            # Show current persona details with additional traits
            persona_display = f"**{self.character_name} Persona:**\n"
            persona_display += f"**Backstory:** {self.character_backstory}\n"
            persona_display += f"**Appearance:** {self.character_description}\n"
            persona_display += f"**Scenario:** {self.character_scenario}\n"
            
            # Add new personality details
            if self.personality_age:
                persona_display += f"**Age:** {self.personality_age}\n"
            if self.personality_traits:
                persona_display += f"**Traits:** {self.personality_traits}\n"
            if self.personality_likes:
                persona_display += f"**Likes:** {self.personality_likes}\n"
            if self.personality_dislikes:
                persona_display += f"**Dislikes:** {self.personality_dislikes}\n"
            if self.personality_tone:
                persona_display += f"**Tone:** {self.personality_tone}\n"
            if self.personality_history:
                history_preview = self.personality_history[:100] + "..." if len(self.personality_history) > 100 else self.personality_history
                persona_display += f"**History:** {history_preview}\n"
            if self.personality_catchphrases:
                persona_display += f"**Catchphrases:** {self.personality_catchphrases}\n"
            if self.jailbreak:
                persona_display += f"**Presets:** {self.jailbreak}\n"
            
            await message.reply(persona_display)

        elif command == "save":
            # Save all data
            self.config_manager.save_config()
            self.memory_manager._save_memory()
            self.lorebook_manager._save_lorebook()
            await message.reply("All data and settings saved!")

        elif command == "help":
            # Show help information
            help_text = "**Out-of-Character Commands:**\n"
            help_text += "- `//memory show` - Display stored memories\n"
            help_text += "- `//memory add Topic: Details` - Add a memory\n"
            help_text += "- `//memory remove Topic` - Remove a memory\n"
            help_text += "- `//memory clear` - Clear all memories\n"
            help_text += "- `//lore add Keyword: Content` - Add a lorebook entry\n"
            help_text += "- `//lore list` - List all lorebook entries\n"
            help_text += "- `//lore remove #` - Remove a lorebook entry by number\n"
            help_text += "- `//lore clear` - Clear all lorebook entries\n"
            help_text += "- `//activate` - Make the bot respond to all messages\n"
            help_text += "- `//deactivate` - Make the bot only respond when called\n"
            help_text += "- `//persona` - Show the current persona details\n"
            help_text += "- `//save` - Save all data and settings\n"
            help_text += "- `//help` - Show this help information\n"
            await message.reply(help_text)

    # Add this as a new method to the OpenShape class
    async def openshape_help_command(self, interaction: discord.Interaction):
        """Display help information about using the OpenShape bot"""
        
        embed = discord.Embed(
            title=f"🤖 {self.character_name} Help Guide",
            description=f"Welcome to the {self.character_name} bot! Here's how to interact with me and make the most of my features.",
            color=0x5865F2
        )
        
        # Basic interaction
        embed.add_field(
            name="💬 Basic Interaction",
            value=(
                f"• **In activated channels:** I respond to all messages automatically\n"
                f"• **In other channels:** @ mention me or say my name ('{self.character_name}')\n"
                f"• **Reactions:** Use 🗑️ to delete my messages, ♻️ to regenerate responses"
            ),
            inline=False
        )
        
        # Character features
        embed.add_field(
            name="🎭 Character Features",
            value=(
                f"• `/character_info` - View my description, traits, and backstory\n"
                f"• `/activate` - Make me respond to all messages in a channel\n"
                f"• `/deactivate` - I'll only respond when mentioned or called by name"
            ),
            inline=False
        )
        
        # Memory system
        embed.add_field(
            name="🧠 Memory System",
            value=(
                f"• I remember important information from our conversations\n"
                f"• `/memory` - View what I've remembered\n"
                f"• `/sleep` - Process recent conversations into long-term memories"
            ),
            inline=False
        )
        
        # Lorebook
        embed.add_field(
            name="📚 Lorebook",
            value=(
                f"• Custom knowledge base that influences my understanding\n"
                f"• `/lorebook` - View entries in the lorebook\n"
                f"• Perfect for worldbuilding and custom knowledge"
            ),
            inline=False
        )
        
        # Owner commands
        if interaction.user.id == self.owner_id:
            embed.add_field(
                name="⚙️ Owner Controls",
                value=(
                    f"• `/settings` - Manage bot behavior settings\n"
                    f"• `/api_settings` - Configure AI API settings\n"
                    f"• `/edit_personality_traits` - Customize character traits\n"
                    f"• `/edit_backstory` - Change character history\n"
                    f"• `/edit_preferences` - Set likes and dislikes\n"
                    f"• `/edit_prompt` - Change system prompt (server specific)\n"
                    f"• `/edit_description` - Modify character description (server specific)\n"
                    f"• `/edit_scenario` - Set interaction scenario (server specific)\n"
                    f"• `/regex` - Manage text pattern manipulation\n"
                    f"• `/blacklist` - Manage user access (server specific)\n"
                    f"• `/save` - Save all current data (server specific)"
                ),
                inline=False
            )
        
        # OOC Commands (owner only)
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
        
        # Tips and best practices
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
        
        # Footer with version
        embed.set_footer(text=f"OpenShapes v0.1 | Designed in https://discord.gg/8QSYftf48j")
        
        await interaction.response.send_message(embed=embed)

# Main function to run the bot
def run_bot(config_path: str):
    """Run the character bot with the specified configuration file"""
    bot = OpenShape(config_path)

    # Get token from config
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    token = config.get("bot_token", "")
    if not token:
        print("Error: No bot token provided in config file.")
        return

    # Run the bot
    bot.run(token)

if __name__ == "__main__":
    # Check if config file exists
    run_bot("character_config.json")
