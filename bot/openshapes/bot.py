import discord
import json
import logging
import os
from typing import Dict, Set, List, Any, Optional
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI
from vectordb.chroma_integration import setup_memory_system
from openshapes.utils.regex_extension import RegexManager
from openshapes.utils.file_parser import FileParser
from openshapes.utils.config_manager import ConfigManager
from openshapes.utils.helpers import OpenShapeHelpers
from openshapes.events.message_handler import on_message, on_reaction_add, OOCCommandHandler
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

class ConfigurationManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

class APIIntegration:
    def __init__(self, api_settings: Dict[str, str]):
        self.base_url = api_settings.get("base_url", "")
        self.api_key = api_settings.get("api_key", "")
        self.chat_model = api_settings.get("chat_model", "")
        self.tts_model = api_settings.get("tts_model", "")
        self.tts_voice = api_settings.get("tts_voice", "")
        self.client = self._initialize_client()
        
    def _initialize_client(self) -> Optional[AsyncOpenAI]:
        if not self.api_key or not self.base_url:
            return None
            
        try:
            return AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=2,
                timeout=60,
            )
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")
            return None
            
    def get_settings(self) -> Dict[str, str]:
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "chat_model": self.chat_model,
            "tts_model": self.tts_model,
            "tts_voice": self.tts_voice
        }

class PersonalityProfile:
    def __init__(self, config: Dict[str, Any]):
        self.name = config.get("character_name", "Assistant")
        self.description = config.get("character_description", "")
        self.backstory = config.get("character_backstory", "")
        self.scenario = config.get("character_scenario", "")
        self.system_prompt = config.get("system_prompt", "")
        self.catchphrases = config.get("personality_catchphrases")
        self.age = config.get("personality_age")
        self.likes = config.get("personality_likes")
        self.dislikes = config.get("personality_dislikes")
        self.goals = config.get("personality_goals")
        self.traits = config.get("personality_traits")
        self.physical_traits = config.get("personality_physical_traits")
        self.tone = config.get("personality_tone")
        self.history = config.get("personality_history")
        self.conversational_goals = config.get("personality_conversational_goals")
        self.conversational_examples = config.get("personality_conversational_examples")
        self.free_will = config.get("free_will", False)
        self.free_will_instruction = config.get("free_will_instruction", "")
        self.jailbreak = config.get("jailbreak", "")

class FileSystemManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.conversations_dir = os.path.join(data_dir, "conversations")
        self.memory_path = os.path.join(data_dir, "memory.json")
        self.lorebook_path = os.path.join(data_dir, "lorebook.json")
        self.audio_dir = os.path.join(data_dir, "audio")
        self._setup_directories()
        
    def _setup_directories(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.conversations_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

class BehaviorSettings:
    def __init__(self, config: Dict[str, Any]):
        self.add_character_name = config.get("add_character_name", True)
        self.always_reply_mentions = config.get("always_reply_mentions", True)
        self.reply_to_name = config.get("reply_to_name", True)
        self.use_tts = config.get("use_tts", False)
        self.activated_channels = set(config.get("activated_channels", []))
        self.blacklisted_users = config.get("blacklisted_users", [])
        self.blacklisted_roles = config.get("blacklisted_roles", [])
        self.conversation_timeout = config.get("conversation_timeout", 30)
        self.message_cooldown_seconds = 3

class CommandRegistry:
    def __init__(self, bot: commands.Bot, allowed_guilds: List[int]):
        self.bot = bot
        self.allowed_guilds = allowed_guilds
        self.tree = bot.tree
        
    def register_global_commands(self) -> None:
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
        
    def register_guild_commands(self) -> None:
        for guild_id in self.allowed_guilds:
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

class OpenShape(commands.Bot):
    def __init__(self, config_path: str, *args, **kwargs):
        self.config_manager = ConfigurationManager(config_path)
        self.character_config = self.config_manager.get("character_config", {})
        intents = discord.Intents.all()
        
        super().__init__(
            command_prefix=self.config_manager.get("command_prefix", "!"),
            intents=intents,
            *args,
            **kwargs,
        )
        
        self.config_path = config_path
        self.owner_id = self.character_config.get("owner_id")
        
        self.api_integration = APIIntegration(self.character_config.get("api_settings", {}))
        self.personality = PersonalityProfile(self.character_config)
        self.file_system = FileSystemManager(self.character_config.get("data_dir", "character_data"))
        self.behavior = BehaviorSettings(self.character_config)
        
        self.channel_conversations = {}
        self.channel_last_message_time = {}

        self._ooc_handler = OOCCommandHandler(self)
        self._handle_ooc_command = self._ooc_handler._handle_ooc_command
        
        self.file_parser = FileParser()
        
        self._initialize_managers()
        
    def _initialize_managers(self) -> None:
        self.config_manager_obj = ConfigManager(self, self.config_path)
        self.helpers = OpenShapeHelpers(self)
        shared_db_path = os.path.join(os.getcwd(), "shared_memory")
        self.memory_manager = setup_memory_system(self, shared_db_path)
        self.regex_manager = RegexManager(self)
        
    @property
    def api_settings(self) -> Dict[str, str]:
        return self.api_integration.get_settings()
        
    @property
    def ai_client(self) -> Optional[AsyncOpenAI]:
        return self.api_integration.client
        
    @property
    def base_url(self) -> str:
        return self.api_integration.base_url
        
    @property
    def api_key(self) -> str:
        return self.api_integration.api_key
        
    @property
    def chat_model(self) -> str:
        return self.api_integration.chat_model
        
    @property
    def tts_model(self) -> str:
        return self.api_integration.tts_model
        
    @property
    def tts_voice(self) -> str:
        return self.api_integration.tts_voice
        
    @property
    def character_name(self) -> str:
        return self.personality.name
        
    @property
    def system_prompt(self) -> str:
        return self.personality.system_prompt
        
    @property
    def character_backstory(self) -> str:
        return self.personality.backstory
        
    @property
    def character_description(self) -> str:
        return self.personality.description
        
    @property
    def character_scenario(self) -> str:
        return self.personality.scenario
        
    @property
    def personality_catchphrases(self) -> Any:
        return self.personality.catchphrases
        
    @property
    def personality_age(self) -> Any:
        return self.personality.age
        
    @property
    def personality_likes(self) -> Any:
        return self.personality.likes
        
    @property
    def personality_dislikes(self) -> Any:
        return self.personality.dislikes
        
    @property
    def personality_goals(self) -> Any:
        return self.personality.goals
        
    @property
    def personality_traits(self) -> Any:
        return self.personality.traits
        
    @property
    def personality_physical_traits(self) -> Any:
        return self.personality.physical_traits
        
    @property
    def personality_tone(self) -> Any:
        return self.personality.tone
        
    @property
    def personality_history(self) -> Any:
        return self.personality.history
        
    @property
    def personality_conversational_goals(self) -> Any:
        return self.personality.conversational_goals
        
    @property
    def personality_conversational_examples(self) -> Any:
        return self.personality.conversational_examples
        
    @property
    def free_will(self) -> bool:
        return self.personality.free_will
        
    @property
    def free_will_instruction(self) -> str:
        return self.personality.free_will_instruction
        
    @property
    def jailbreak(self) -> str:
        return self.personality.jailbreak
        
    @property
    def data_dir(self) -> str:
        return self.file_system.data_dir
        
    @property
    def conversations_dir(self) -> str:
        return self.file_system.conversations_dir
        
    @property
    def memory_path(self) -> str:
        return self.file_system.memory_path
        
    @property
    def lorebook_path(self) -> str:
        return self.file_system.lorebook_path
        
    @property
    def audio_dir(self) -> str:
        return self.file_system.audio_dir
        
    @property
    def add_character_name(self) -> bool:
        return self.behavior.add_character_name
        
    @property
    def always_reply_mentions(self) -> bool:
        return self.behavior.always_reply_mentions
        
    @property
    def reply_to_name(self) -> bool:
        return self.behavior.reply_to_name
        
    @property
    def use_tts(self) -> bool:
        return self.behavior.use_tts
        
    @property
    def activated_channels(self) -> Set[int]:
        return self.behavior.activated_channels
        
    @property
    def blacklisted_users(self) -> List[int]:
        return self.behavior.blacklisted_users
        
    @property
    def blacklisted_roles(self) -> List[int]:
        return self.behavior.blacklisted_roles
        
    @property
    def conversation_timeout(self) -> int:
        return self.behavior.conversation_timeout
        
    @property
    def message_cooldown_seconds(self) -> int:
        return self.behavior.message_cooldown_seconds
        
    async def setup_hook(self) -> None:
        command_registry = CommandRegistry(self, self.character_config.get("allowed_guilds", []))
        command_registry.register_global_commands()
        command_registry.register_guild_commands()
        
        self.add_listener(on_message, "on_message")
        self.add_listener(on_reaction_add, "on_reaction_add")

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        await self.tree.sync()
        logger.info(f"Character name: {self.character_name}")
