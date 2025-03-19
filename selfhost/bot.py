import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
import re
import os
import datetime
from typing import Dict, List, Optional, Any
from openai import OpenAI
import asyncio
import aiohttp
import io


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple_character_bot")


class SimpleCharacterBot(commands.Bot):
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
        self.character_description = self.character_config.get(
            "character_description", ""
        )
        self.character_personality = self.character_config.get(
            "character_personality", ""
        )
        self.character_scenario = self.character_config.get("character_scenario", "")

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
                self.ai_client = OpenAI(
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

        # Initialize storage
        self._load_storage()

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

    def _load_storage(self):
        """Load memory and lorebook from files"""
        # Load memory
        if os.path.exists(self.memory_path):
            with open(self.memory_path, "r", encoding="utf-8") as f:
                self.long_term_memory = json.load(f)
        else:
            self.long_term_memory = {}
            self._save_memory()

        # Load lorebook
        if os.path.exists(self.lorebook_path):
            with open(self.lorebook_path, "r", encoding="utf-8") as f:
                self.lorebook_entries = json.load(f)
        else:
            self.lorebook_entries = []
            self._save_lorebook()

    def _save_memory(self):
        """Save memory to file"""
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.long_term_memory, f, indent=2)

    def _save_lorebook(self):
        """Save lorebook to file"""
        with open(self.lorebook_path, "w", encoding="utf-8") as f:
            json.dump(self.lorebook_entries, f, indent=2)

    def _save_config(self):
        """Save configuration to file"""
        # Update config with current settings
        self.character_config.update(
            {
                "character_name": self.character_name,
                "system_prompt": self.system_prompt,
                "character_description": self.character_description,
                "character_personality": self.character_personality,
                "character_scenario": self.character_scenario,
                "add_character_name": self.add_character_name,
                "reply_to_name": self.reply_to_name,
                "always_reply_mentions": self.always_reply_mentions,
                "activated_channels": list(self.activated_channels),
                "blacklisted_users": self.blacklisted_users,
                "blacklisted_roles": self.blacklisted_roles,
            }
        )

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.character_config, f, indent=2)

    def _save_conversation(self, channel_id, conversation):
        """Save a conversation to a JSON file"""
        # Create a filename with channel ID and timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{channel_id}_{timestamp}.json"
        filepath = os.path.join(self.conversations_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(conversation, f, indent=2)

    async def setup_hook(self):
        """Register slash commands when the bot is starting up"""
        # Basic commands
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
                    name="edit_personality",
                    description="Edit the character's personality",
                    callback=self.edit_personality_command,
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
        embed = discord.Embed(title=f"{self.character_name} Info", color=0x3498DB)
        embed.add_field(
            name="Description",
            value=self.character_description[:1024] or "No description set",
            inline=False,
        )
        embed.add_field(
            name="Personality",
            value=self.character_personality[:1024] or "No personality set",
            inline=False,
        )
        if self.character_scenario:
            embed.add_field(
                name="Scenario", value=self.character_scenario[:1024], inline=False
            )

        await interaction.response.send_message(embed=embed)

    async def activate_command(self, interaction: discord.Interaction):
        """Activate the bot in the current channel"""
        self.activated_channels.add(interaction.channel_id)
        self._save_config()
        await interaction.response.send_message(
            f"{self.character_name} will now respond to all messages in this channel."
        )

    async def deactivate_command(self, interaction: discord.Interaction):
        """Deactivate the bot in the current channel"""
        if interaction.channel_id in self.activated_channels:
            self.activated_channels.remove(interaction.channel_id)
            self._save_config()
        await interaction.response.send_message(
            f"{self.character_name} will now only respond when mentioned or called by name."
        )

    async def memory_command(self, interaction: discord.Interaction):
        """View or manage memories"""
        # Only allow the owner to manage memories
        if interaction.user.id != self.owner_id:
            memory_display = "**Long-term Memory:**\n"
            if not self.long_term_memory:
                memory_display += "No memories stored yet."
            else:
                for topic, details in self.long_term_memory.items():
                    memory_display += f"- **{topic}**: {details}\n"

            await interaction.response.send_message(memory_display)
            return

        # Create a view for memory management
        view = MemoryManagementView(self)

        memory_display = "**Long-term Memory:**\n"
        if not self.long_term_memory:
            memory_display += "No memories stored yet."
        else:
            for topic, details in self.long_term_memory.items():
                memory_display += f"- **{topic}**: {details}\n"

        await interaction.response.send_message(memory_display, view=view)

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
                self.character_config["use_tts"] = self.use_tts
                self._save_config()
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
                    completion = await self._call_chat_api(
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
                    self.character_config["api_settings"] = self.api_settings
                    self._save_config()

                    # Reinitialize OpenAI client if base URL and API key are set
                    if self.api_key and self.base_url:
                        try:
                            self.ai_client = OpenAI(
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

    async def _call_chat_api(
        self,
        user_message,
        user_name="User",
        conversation_history=None,
        relevant_lore=None,
    ):
        """Call the AI API to generate a response"""
        if not self.ai_client or not self.chat_model:
            return None

        try:
            # Build system prompt with character info
            system_content = f"""You are {self.character_name}.
    Description: {self.character_description}
    Personality: {self.character_personality}
    Scenario: {self.character_scenario}
    """

            # Add any custom system prompt
            if self.system_prompt:
                system_content += f"\n{self.system_prompt}"

            # Add relevant lore if available
            if relevant_lore and len(relevant_lore) > 0:
                system_content += "\nImportant information you know:\n"
                for lore in relevant_lore:
                    system_content += f"- {lore}\n"

            # Prepare messages list
            messages = [{"role": "system", "content": system_content}]

            # Add conversation history (limited to last 10 messages)
            if conversation_history:
                for entry in conversation_history[-10:]:
                    role = "assistant" if entry["role"] == "assistant" else "user"
                    messages.append({"role": role, "content": entry["content"]})

            # If the latest message isn't in history, add it
            if not conversation_history or user_message != conversation_history[-1].get(
                "content", ""
            ):
                messages.append({"role": "user", "content": user_message})

            # Call API
            completion = self.ai_client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                stream=False,
            )

            # Extract response text
            response = completion.choices[0].message.content
            return response

        except Exception as e:
            logger.error(f"Error calling chat API: {e}")
            return f"I'm having trouble connecting to my thoughts right now. Please try again later. (Error: {str(e)[:50]}...)"

    # Add a method to generate TTS audio
    async def _generate_tts(self, text):
        """Generate TTS audio from text"""
        if (
            not self.ai_client
            or not self.tts_model
            or not self.tts_voice
            or not self.use_tts
        ):
            return None

        try:
            # Generate a filename based on text hash
            import hashlib

            text_hash = hashlib.md5(text.encode()).hexdigest()[:10]
            filename = f"{self.character_name}_{text_hash}.mp3"
            filepath = os.path.join(self.audio_dir, filename)

            # Check if file already exists
            if os.path.exists(filepath):
                return filepath

            # Call TTS API
            response = self.ai_client.audio.speech.create(
                model=self.tts_model, voice=self.tts_voice, input=text
            )

            # Save audio file
            response.stream_to_file(filepath)
            return filepath

        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None

    # Modify the _generate_res
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

        lore_display = "**Lorebook Entries:**\n"
        if not self.lorebook_entries:
            lore_display += "No entries yet."
        else:
            for i, entry in enumerate(self.lorebook_entries):
                lore_display += (
                    f"{i+1}. **{entry['keyword']}**: {entry['content'][:50]}...\n"
                )

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
            self._save_config()
            await modal_interaction.response.send_message(
                "System prompt updated!", ephemeral=True
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
            self._save_config()
            await modal_interaction.response.send_message(
                "Character description updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    async def edit_personality_command(self, interaction: discord.Interaction):
        """Edit the character's personality"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
        modal = TextEditModal(
            title="Edit Personality", current_text=self.character_personality
        )

        async def on_submit(modal_interaction):
            self.character_personality = modal.text_input.value
            self._save_config()
            await modal_interaction.response.send_message(
                "Character personality updated!", ephemeral=True
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
            self._save_config()
            await modal_interaction.response.send_message(
                "Character scenario updated!", ephemeral=True
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
                            self._save_config()
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
                            self._save_config()
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
        self._save_config()
        self._save_memory()
        self._save_lorebook()

        await interaction.response.send_message(
            "All data and settings saved!", ephemeral=True
        )

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        await self.tree.sync()
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

        if should_respond:
            async with message.channel.typing():
                # Remove mentions from the message
                clean_content = re.sub(r"<@!?(\d+)>", "", message.content).strip()

                # Get conversation history for this channel
                channel_history = self._get_channel_conversation(message.channel.id)

                # Add the new message to history
                channel_history.append(
                    {
                        "role": "user",
                        "name": message.author.display_name,
                        "content": clean_content,
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                )

                # Get relevant lorebook entries
                relevant_lore = self._get_relevant_lorebook_entries(clean_content)

                # Generate a response based on persona and history
                response = await self._generate_response(
                    message.author.display_name,
                    clean_content,
                    channel_history,
                    relevant_lore,
                )

                # Add response to history
                channel_history.append(
                    {
                        "role": "assistant",
                        "name": self.character_name,
                        "content": response,
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                )

                # Save conversation periodically (every 10 messages)
                if len(channel_history) >= 10:
                    self._save_conversation(message.channel.id, channel_history)
                    channel_history = []  # Reset after saving

                # Format response with name if enabled
                formatted_response = (
                    f"**{self.character_name}**: {response}"
                    if self.add_character_name
                    else response
                )

                # Send the response and add reaction for deletion
                if not self.use_tts:
                    sent_message = await message.reply(formatted_response)
                    await sent_message.add_reaction("🗑️")

                # Generate and send TTS if enabled
                if self.use_tts and message.guild:
                    audio_file = await self._generate_tts(response)
                    if audio_file:
                        try:
                            # Check if user is in a voice channel
                            if message.author.voice and message.author.voice.channel:
                                voice_channel = message.author.voice.channel

                                # Connect to voice channel
                                voice_client = message.guild.voice_client
                                if voice_client:
                                    if voice_client.channel != voice_channel:
                                        await voice_client.move_to(voice_channel)
                                else:
                                    voice_client = await voice_channel.connect()

                                # Play audio
                                voice_client.play(
                                    discord.FFmpegPCMAudio(audio_file),
                                    after=lambda e: asyncio.run_coroutine_threadsafe(
                                        self._disconnect_after_audio(voice_client),
                                        self.loop,
                                    ),
                                )
                        except Exception as e:
                            logger.error(f"Error playing TTS audio: {e}")

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle reactions to messages"""
        # If the reaction is the trash emoji on the bot's message and from message author or bot owner
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
            await reaction.message.delete()

    async def _handle_ooc_command(self, message: discord.Message):
        """Handle out-of-character commands from the owner"""
        clean_content = message.content.replace("//", "").replace("/ooc", "").strip()
        parts = clean_content.split(" ", 1)
        command = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        if command == "memory":
            if args.lower() == "show":
                memory_display = "**Long-term Memory:**\n"
                if not self.long_term_memory:
                    memory_display += "No memories stored yet."
                else:
                    for topic, details in self.long_term_memory.items():
                        memory_display += f"- **{topic}**: {details}\n"
                await message.reply(memory_display)
            elif args.lower().startswith("add "):
                # Add memory manually
                mem_parts = args[4:].split(":", 1)
                if len(mem_parts) == 2:
                    topic, details = mem_parts
                    self.long_term_memory[topic.strip()] = details.strip()
                    self._save_memory()
                    await message.reply(f"Added memory: {topic.strip()}")
                else:
                    await message.reply(
                        "Invalid format. Use: //memory add Topic: Details"
                    )
            elif args.lower().startswith("remove "):
                # Remove memory
                topic = args[7:].strip()
                if topic in self.long_term_memory:
                    del self.long_term_memory[topic]
                    self._save_memory()
                    await message.reply(f"Removed memory: {topic}")
                else:
                    await message.reply(f"Memory topic '{topic}' not found.")
            elif args.lower() == "clear":
                self.long_term_memory = {}
                self._save_memory()
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
                    self.lorebook_entries.append(
                        {"keyword": keyword.strip(), "content": content.strip()}
                    )
                    self._save_lorebook()
                    await message.reply(
                        f"Added lorebook entry for keyword: {keyword.strip()}"
                    )
                else:
                    await message.reply(
                        "Invalid format. Use: //lore add Keyword: Content"
                    )
            elif subcommand == "list":
                lore_display = "**Lorebook Entries:**\n"
                if not self.lorebook_entries:
                    lore_display += "No entries yet."
                else:
                    for i, entry in enumerate(self.lorebook_entries):
                        lore_display += f"{i+1}. **{entry['keyword']}**: {entry['content'][:50]}...\n"
                await message.reply(lore_display)
            elif subcommand == "remove" and subargs:
                try:
                    index = int(subargs) - 1
                    if 0 <= index < len(self.lorebook_entries):
                        removed = self.lorebook_entries.pop(index)
                        self._save_lorebook()
                        await message.reply(
                            f"Removed lorebook entry for: {removed['keyword']}"
                        )
                    else:
                        await message.reply("Invalid entry number.")
                except ValueError:
                    await message.reply("Please provide a valid entry number.")
            elif subcommand == "clear":
                self.lorebook_entries = []
                self._save_lorebook()
                await message.reply("All lorebook entries cleared.")

        elif command == "activate":
            self.activated_channels.add(message.channel.id)
            self._save_config()
            await message.reply(
                f"{self.character_name} will now respond to all messages in this channel."
            )

        elif command == "deactivate":
            if message.channel.id in self.activated_channels:
                self.activated_channels.remove(message.channel.id)
                self._save_config()
            await message.reply(
                f"{self.character_name} will now only respond when mentioned or called by name."
            )

        elif command == "persona":
            # Show current persona details
            persona_display = f"**{self.character_name} Persona:**\n"
            persona_display += f"**Description:** {self.character_description}\n"
            persona_display += f"**Personality:** {self.character_personality}\n"
            persona_display += f"**Scenario:** {self.character_scenario}\n"
            await message.reply(persona_display)

        elif command == "save":
            # Save all data
            self._save_config()
            self._save_memory()
            self._save_lorebook()
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

    def _get_channel_conversation(self, channel_id: int) -> List[Dict]:
        """Get conversation history for a specific channel"""
        # This would normally load from a database or file
        # For simplicity, we'll just maintain in-memory conversation history
        if not hasattr(self, "channel_conversations"):
            self.channel_conversations = {}

        if channel_id not in self.channel_conversations:
            self.channel_conversations[channel_id] = []

        return self.channel_conversations[channel_id]

    def _get_relevant_lorebook_entries(self, message_content: str) -> List[str]:
        """Get lorebook entries relevant to the current message"""
        relevant_entries = []

        for entry in self.lorebook_entries:
            # Check if keyword is in the message
            if entry["keyword"].lower() in message_content.lower():
                relevant_entries.append(entry["content"])

        return relevant_entries

    async def _generate_response(
        self,
        user_name: str,
        message_content: str,
        conversation_history: List[Dict],
        relevant_lore: List[str] = None,
    ) -> str:
        """
        Generate a response using the AI API if configured, otherwise fall back to simple responses.
        """
        # Try to use the API first if configured
        if self.ai_client and self.chat_model:
            response = await self._call_chat_api(
                message_content, user_name, conversation_history, relevant_lore
            )
            if response:
                return response

        # Fallback to the original simple response logic
        # Build a prompt using character information and history
        prompt = f"""Character: {self.character_name}
            Description: {self.character_description}
            Personality: {self.character_personality}
            Scenario: {self.character_scenario}

            User: {user_name}
            Message: {message_content}
            """
        # Add relevant lorebook entries
        if relevant_lore and len(relevant_lore) > 0:
            prompt += "Relevant information:\n"
            for lore in relevant_lore:
                prompt += f"- {lore}\n"

        # Add conversation history context
        if len(conversation_history) > 1:
            prompt += "\nRecent conversation:\n"
            for entry in conversation_history[-4:-1]:  # Skip the current message
                prompt += f"{entry['name']}: {entry['content']}\n"

        # Detect basic greeting patterns
        greeting_words = ["hello", "hi", "hey", "greetings", "howdy"]
        if any(word in message_content.lower() for word in greeting_words):
            return f"Hello {user_name}! How can I help you today?"

        # Detect questions
        if "?" in message_content:
            return f"That's an interesting question! Let me think about that..."

        # Default response
        return f"I understand you're saying something about '{message_content[:20]}...'. As {self.character_name}, I would respond appropriately based on my personality and our conversation history."

    # Add helper method for voice disconnection

    async def _disconnect_after_audio(self, voice_client):
        """Disconnect from voice channel after audio finishes playing"""
        # Wait a moment to ensure audio is fully played
        await asyncio.sleep(1)

        # Check if still playing
        if voice_client and not voice_client.is_playing():
            await voice_client.disconnect()


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
    async def add_memory(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = MemoryEntryModal()

        async def on_submit(modal_interaction):
            topic = modal.topic_input.value
            details = modal.details_input.value
            self.bot.long_term_memory[topic] = details
            self.bot._save_memory()
            await modal_interaction.response.send_message(
                f"Added memory: {topic}", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Clear All Memory", style=discord.ButtonStyle.danger)
    async def clear_memory(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
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


# Main function to run the bot
def run_bot(config_path: str):
    """Run the character bot with the specified configuration file"""
    bot = SimpleCharacterBot(config_path)

    # Get token from config
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    token = config.get("bot_token", "")
    if not token:
        print("Error: No bot token provided in config file.")
        return

    # Run the bot
    bot.run(token)


# Example configuration structure and usage
example_config = {
    "bot_token": "YOUR_BOT_TOKEN_HERE",
    "owner_id": 123456789012345678,
    "character_name": "Luna",
    "allowed_guilds": [123456789012345678],
    "command_prefix": "!",
    "system_prompt": "You're a helpful assistant named Luna.",
    "character_description": "Luna is a friendly AI assistant who loves helping people.",
    "character_personality": "Cheerful, kind, and always eager to help.",
    "character_scenario": "Luna is in a Discord server answering questions for users.",
    "add_character_name": True,
    "reply_to_name": True,
    "always_reply_mentions": True,
    "use_tts": False,
    "data_dir": "character_data",
    "api_settings": {
        "base_url": "",
        "api_key": "",
        "chat_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
}

if __name__ == "__main__":
    # Check if config file exists
    config_path = "character_config.json"

    if not os.path.exists(config_path):
        # Create a default config file
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(example_config, f, indent=2)
        print(f"Created default config file at {config_path}")
        print("Please edit this file with your bot token and settings.")
    else:
        # Run the bot with the existing config
        run_bot(config_path)
