import json
import logging
import os
import discord
from typing import Dict, Set, List, Any, Optional
from discord.ext import commands
from openai import AsyncOpenAI
try:
    from openshapes.vectordb.chroma_integration import MemorySystem
    from openshapes.vectordb.chroma_preload import preload_chromadb_model
    from openshapes.utils.regex_extension import RegexManager
    from openshapes.utils.file_parser import FileParser
    from openshapes.utils.config_manager import ConfigManager
    from openshapes.utils.helpers import OpenShapeHelpers
    from openshapes.events import MessageHandler, ReactionHandler, OOCCommandHandler
except ImportError:
    from vectordb.chroma_integration import MemorySystem
    from vectordb.chroma_preload import preload_chromadb_model
    from utils.regex_extension import RegexManager
    from utils.file_parser import FileParser
    from utils.config_manager import ConfigManager
    from utils.helpers import OpenShapeHelpers
    from events import MessageHandler, ReactionHandler, OOCCommandHandler
    

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openshape")

class ConfigurationManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.data = {}
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
                logger.info(f"Successfully loaded config from {self.config_path}")
                return self.data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def save_config(self) -> None:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
                logger.info(f"Saved config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def update_field(self, key: str, value: Any) -> None:
        self.data[key] = value

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
                timeout=60
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
        self.free_will = config.get("free_will")
        self.free_will_instruction = config.get("free_will_instruction")
        self.jailbreak = config.get("jailbreak")

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
        self.message_cooldown_seconds = config.get("message_cooldown_seconds", 3)

class OpenShape(commands.Bot):
    def __init__(self, config_path: str, *args, **kwargs):
        self.config_manager = ConfigurationManager(config_path)
        intents = discord.Intents.all()
        
        super().__init__(
            command_prefix=self.config_manager.get("command_prefix", "!"),
            intents=intents,
            *args,
            **kwargs,
        )
        
        self.config_path = config_path
        
        self.api_integration = APIIntegration(self.config_manager.get("api_settings", {}))
        self.personality = PersonalityProfile(self.config_manager.data)
        self.file_system = FileSystemManager(self.config_manager.get("data_dir", "character_data"))
        self.behavior = BehaviorSettings(self.config_manager.data)
        
        self.channel_conversations = {}
        self.channel_last_message_time = {}

        self._reaction_handler = ReactionHandler(self)
        self._message_handler = MessageHandler(self)

        self._ooc_handler = OOCCommandHandler(self)
        self._handle_ooc_command = self._ooc_handler._handle_ooc_command
        
        self.file_parser = FileParser()
        
        self.config_manager_obj = ConfigManager(self)
        self.helpers = OpenShapeHelpers(self)
        self.regex_manager = RegexManager(self)

        self.memory_setup_handler = MemorySystem(self, os.path.join(os.getcwd(), "shared_memory"))
        self.memory_setup_handler.setup()

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
    def message_cooldown_seconds(self) -> int:
        return self.behavior.message_cooldown_seconds

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        self.personality.system_prompt = value

    @character_description.setter
    def character_description(self, value: str) -> None:
        self.personality.description = value

    @character_scenario.setter
    def character_scenario(self, value: str) -> None:
        self.personality.scenario = value

    @personality_catchphrases.setter
    def personality_catchphrases(self, value: Any) -> None:
        self.personality.catchphrases = value

    @personality_age.setter
    def personality_age(self, value: Any) -> None:
        self.personality.age = value

    @personality_likes.setter
    def personality_likes(self, value: Any) -> None:
        self.personality.likes = value

    @personality_dislikes.setter
    def personality_dislikes(self, value: Any) -> None:
        self.personality.dislikes = value

    @personality_goals.setter
    def personality_goals(self, value: Any) -> None:
        self.personality.goals = value

    @personality_traits.setter
    def personality_traits(self, value: Any) -> None:
        self.personality.traits = value

    @personality_physical_traits.setter
    def personality_physical_traits(self, value: Any) -> None:
        self.personality.physical_traits = value

    @personality_tone.setter
    def personality_tone(self, value: Any) -> None:
        self.personality.tone = value

    @personality_history.setter
    def personality_history(self, value: Any) -> None:
        self.personality.history = value

    @personality_conversational_goals.setter
    def personality_conversational_goals(self, value: Any) -> None:
        self.personality.conversational_goals = value

    @personality_conversational_examples.setter
    def personality_conversational_examples(self, value: Any) -> None:
        self.personality.conversational_examples = value

    @add_character_name.setter
    def add_character_name(self, value: bool) -> None:
        self.behavior.add_character_name = value

    @always_reply_mentions.setter
    def always_reply_mentions(self, value: bool) -> None:
        self.behavior.always_reply_mentions = value

    @reply_to_name.setter
    def reply_to_name(self, value: bool) -> None:
        self.behavior.reply_to_name = value

    @use_tts.setter
    def use_tts(self, value: bool) -> None:
        self.behavior.use_tts = value

    @activated_channels.setter
    def activated_channels(self, value: Set[int]) -> None:
        self.behavior.activated_channels = value

    @blacklisted_users.setter
    def blacklisted_users(self, value: List[int]) -> None:
        self.behavior.blacklisted_users = value

    @message_cooldown_seconds.setter
    def message_cooldown_seconds(self, value: int) -> None:
        self.behavior.message_cooldown_seconds = value
    
    async def register_cogs(self) -> None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        cogs_dir = os.path.join(current_dir, "cogs")
        if os.path.exists(cogs_dir):
            import sys
            parent_dir = os.path.dirname(current_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            for file in os.listdir(cogs_dir):
                if file.endswith(".py") and not file.startswith("__"):
                    await self.load_extension(f"openshapes.cogs.{file[:-3]}")
        else:
            logger.warning(f"Cogs directory not found at: {cogs_dir}")

    async def setup_hook(self) -> None:
        await self.register_cogs()
        
        self.add_listener(self._message_handler.on_message, "on_message")
        self.add_listener(self._reaction_handler.on_reaction_add, "on_reaction_add")
        
        if hasattr(self, 'memory_manager') and self.memory_manager:
            try:
                self.loop.create_task(preload_chromadb_model(self.memory_manager))
                logger.info("Scheduled ChromaDB model preloading during bot initialization")
            except ImportError:
                logger.warning("ChromaDB preload module not found, model will be loaded on first memory operation")

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        await self.tree.sync()
        logger.info(f"Character name: {self.character_name}")

    async def close(self):
        self.config_manager.save_config()
        return await super().close()