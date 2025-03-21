import discord
import json
import logging
import os

from discord import app_commands
from discord.ext import commands

from openai import AsyncOpenAI

from openshapes.utils.regex_extension import RegexManager
from openshapes.utils.file_parser import FileParser
from openshapes.utils.config_manager import ConfigManager
from openshapes.utils.helpers import OpenShapeHelpers

from vectordb.chroma_integration import setup_memory_system

from openshapes.events.message_handler import on_message, on_reaction_add, _handle_ooc_command
from openshapes.commands.basic_commands import (
    character_info_command,
    activate_command,
    deactivate_command,
    models_command
)
from openshapes.commands.personality_commands import (
    edit_personality_traits_command,
    edit_backstory_command,
    edit_preferences_command
)
from openshapes.commands.memory_commands import sleep_command, memory_command 
from openshapes.commands.api_commands import api_settings_command
from openshapes.commands.lorebook_commands import lorebook_command
from openshapes.commands.settings_commands import (
    settings_command,
    edit_prompt_command,
    edit_description_command,
    edit_scenario_command,
    blacklist_command,
    save_command,
    regex_command,
    openshape_help_command
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openshape")

class OpenShape(commands.Bot):
    def __init__(self, config_path: str, *args, **kwargs):
        with open(config_path, "r", encoding="utf-8") as f:
            self.character_config = json.load(f)

        intents = discord.Intents.all()

        super().__init__(
            command_prefix=self.character_config.get("command_prefix", "!"),
            intents=intents,
            *args,
            **kwargs,
        )

        self.config_path = config_path
        self.owner_id = self.character_config.get("owner_id")
        self.character_name = self.character_config.get("character_name", "Assistant")

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
        self.file_parser = FileParser()
        
        self.api_settings = self.character_config.get("api_settings", {})
        self.base_url = self.api_settings.get("base_url", "")
        self.api_key = self.api_settings.get("api_key", "")
        self.chat_model = self.api_settings.get("chat_model", "")
        self.tts_model = self.api_settings.get("tts_model", "")
        self.tts_voice = self.api_settings.get("tts_voice", "")

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

        self.data_dir = self.character_config.get("data_dir", "character_data")
        self.conversations_dir = os.path.join(self.data_dir, "conversations")
        self.memory_path = os.path.join(self.data_dir, "memory.json")
        self.lorebook_path = os.path.join(self.data_dir, "lorebook.json")
        self.audio_dir = os.path.join(self.data_dir, "audio")

        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.conversations_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

        self.add_character_name = self.character_config.get("add_character_name", True)
        self.always_reply_mentions = self.character_config.get(
            "always_reply_mentions", True
        )
        self.reply_to_name = self.character_config.get("reply_to_name", True)
        self.activated_channels = set(
            self.character_config.get("activated_channels", [])
        )
        self.use_tts = self.character_config.get("use_tts", False)

        self.blacklisted_users = self.character_config.get("blacklisted_users", [])
        self.blacklisted_roles = self.character_config.get("blacklisted_roles", [])
        self.conversation_timeout = self.character_config.get("conversation_timeout", 30)

        self.config_manager = ConfigManager(self, config_path)
        self.helpers = OpenShapeHelpers(self)
        
        shared_db_path = os.path.join(os.getcwd(), "shared_memory")
        self.memory_manager = setup_memory_system(self, shared_db_path)
        
        self.regex_manager = RegexManager(self)
        
        self.channel_conversations = {}
        
        self.channel_last_message_time = {}
        self.message_cooldown_seconds = 3
        
        self._handle_ooc_command = _handle_ooc_command

    async def setup_hook(self):
        self.tree.add_command(
            app_commands.Command(
                name="openshapes",
                description="Get help and learn how to use OpenShape bot",
                callback=openshape_help_command,
            )
        )
        
        self.tree.add_command(
            app_commands.Command(
                name="api_settings",
                description="Configure AI API settings",
                callback=api_settings_command,
            ),
        )

        self.tree.add_command(
            app_commands.Command(
                name="character_info",
                description="Show information about this character",
                callback=character_info_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="activate",
                description="Activate the bot to respond to all messages in the channel",
                callback=activate_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="deactivate",
                description="Deactivate the bot's automatic responses in the channel",
                callback=deactivate_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="memory",
                description="View or manage the character's memory",
                callback=memory_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="lorebook",
                description="Manage lorebook entries",
                callback=lorebook_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="settings",
                description="Manage character settings",
                callback=settings_command,
            )
        )
        
        self.tree.add_command(
            app_commands.Command(
                name="models",
                description="Change the AI model used by the bot",
                callback=models_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="edit_personality_traits",
                description="Edit specific personality traits for the character",
                callback=edit_personality_traits_command,
            ),
        )
        
        self.tree.add_command(
            app_commands.Command(
                name="edit_backstory",
                description="Edit the character's history and background",
                callback=edit_backstory_command,
            ),
        )
        
        self.tree.add_command(
            app_commands.Command(
                name="edit_preferences",
                description="Edit what the character likes and dislikes",
                callback=edit_preferences_command,
            ),
        )

        self.tree.add_command(
            app_commands.Command(
                name="sleep",
                description="Generate a long term memory.",
                callback=sleep_command,
            ),
        )

        self.tree.add_command(
            app_commands.Command(
                name="regex",
                description="Manage RegEx pattern scripts for text manipulation",
                callback=regex_command,
            )
        )

        for guild_id in self.character_config.get("allowed_guilds", []):
            guild = discord.Object(id=guild_id)

            self.tree.add_command(
                app_commands.Command(
                    name="edit_prompt",
                    description="Edit the character's system prompt",
                    callback=edit_prompt_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="edit_description",
                    description="Edit the character's description",
                    callback=edit_description_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="edit_scenario",
                    description="Edit the character's scenario",
                    callback=edit_scenario_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="blacklist",
                    description="Add or remove a user from the blacklist",
                    callback=blacklist_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="save",
                    description="Save all current settings and data",
                    callback=save_command,
                ),
                guild=guild,
            )
        
        self.add_listener(on_message, "on_message")
        self.add_listener(on_reaction_add, "on_reaction_add")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        await self.tree.sync()
        logger.info(f"Character name: {self.character_name}")
