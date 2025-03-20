import json
import os
import logging
from typing import Any, Dict, List, Optional, Union

# Configure logging
logger = logging.getLogger("openshape.config")

class ConfigManager:
    """Manages configuration loading, saving, and validation"""
    def __init__(self, bot, config_path: str):
        self.bot = bot
        self.config_path = config_path
        self.default_config = {
            "bot_token": "",
            "command_prefix": "!",
            "owner_id": None,
            "character_name": "Assistant",
            "system_prompt": "",
            "character_backstory": "",
            "character_description": "",
            "character_scenario": "",
            "personality_catchphrases": "",
            "personality_age": "",
            "personality_likes": "",
            "personality_dislikes": "",
            "personality_goals": "",
            "personality_traits": "",
            "personality_physical_traits": "",
            "personality_tone": "",
            "personality_history": "",
            "personality_conversational_goals": "",
            "personality_conversational_examples": "",
            "free_will": False,
            "free_will_instruction": "",
            "jailbreak": "",
            "add_character_name": True,
            "always_reply_mentions": True,
            "reply_to_name": True,
            "use_tts": False,
            "activated_channels": [],
            "allowed_guilds": [],
            "blacklisted_users": [],
            "blacklisted_roles": [],
            "conversation_timeout": 30,
            "api_settings": {
                "base_url": "",
                "api_key": "",
                "chat_model": "",
                "tts_model": "",
                "tts_voice": ""
            },
            "data_dir": "character_data"
        }
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file with fallback to defaults"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    
                # Ensure all required fields exist by merging with defaults
                merged_config = self.default_config.copy()
                merged_config.update(config)
                
                # Ensure API settings are properly structured
                if "api_settings" not in merged_config:
                    merged_config["api_settings"] = self.default_config["api_settings"]
                elif isinstance(merged_config["api_settings"], dict):
                    default_api = self.default_config["api_settings"].copy()
                    default_api.update(merged_config["api_settings"])
                    merged_config["api_settings"] = default_api
                    
                return merged_config
            else:
                # No config exists, create a new one with defaults
                logger.warning(f"No configuration file found at {self.config_path}. Using default configuration.")
                self.save_config(self.default_config)
                return self.default_config
                
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return self.default_config
            
    def save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Save configuration to file"""
        try:
            # If no config provided, build from bot attributes
            if config is None:
                config = self.build_config_from_bot()
                
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                
            logger.info("Configuration saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False
            
    def build_config_from_bot(self) -> Dict[str, Any]:
        """Build a config dictionary from the bot's current attributes"""
        config = {
            "command_prefix": self.bot.command_prefix,
            "owner_id": self.bot.owner_id,
            "character_name": self.bot.character_name,
            "system_prompt": self.bot.system_prompt,
            "character_backstory": self.bot.character_backstory,
            "character_description": self.bot.character_description,
            "character_scenario": self.bot.character_scenario,
            "personality_catchphrases": self.bot.personality_catchphrases,
            "personality_age": self.bot.personality_age,
            "personality_likes": self.bot.personality_likes,
            "personality_dislikes": self.bot.personality_dislikes,
            "personality_goals": self.bot.personality_goals,
            "personality_traits": self.bot.personality_traits,
            "personality_physical_traits": self.bot.personality_physical_traits,
            "personality_tone": self.bot.personality_tone,
            "personality_history": self.bot.personality_history,
            "personality_conversational_goals": self.bot.personality_conversational_goals,
            "personality_conversational_examples": self.bot.personality_conversational_examples,
            "free_will": self.bot.free_will,
            "free_will_instruction": self.bot.free_will_instruction,
            "jailbreak": self.bot.jailbreak,
            "add_character_name": self.bot.add_character_name,
            "always_reply_mentions": self.bot.always_reply_mentions,
            "reply_to_name": self.bot.reply_to_name,
            "use_tts": self.bot.use_tts,
            "activated_channels": list(self.bot.activated_channels),
            "blacklisted_users": self.bot.blacklisted_users,
            "blacklisted_roles": self.bot.blacklisted_roles,
            "conversation_timeout": self.bot.conversation_timeout,
            "api_settings": self.bot.api_settings,
            "data_dir": self.bot.data_dir
        }
        
        # If the bot has allowed_guilds attribute, include that
        if hasattr(self.bot, "allowed_guilds"):
            config["allowed_guilds"] = self.bot.allowed_guilds
            
        # Keep the bot token if it exists in the original config
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                original_config = json.load(f)
                if "bot_token" in original_config:
                    config["bot_token"] = original_config["bot_token"]
        except:
            pass
            
        return config
        
    def update_bot_from_config(self, config: Dict[str, Any]) -> None:
        """Update the bot's attributes from a config dictionary"""
        # Basic character settings
        self.bot.character_name = config.get("character_name", "Assistant")
        self.bot.owner_id = config.get("owner_id")
        self.bot.command_prefix = config.get("command_prefix", "!")
        
        # Persona settings
        self.bot.system_prompt = config.get("system_prompt", "")
        self.bot.character_backstory = config.get("character_backstory", "")
        self.bot.character_description = config.get("character_description", "")
        self.bot.character_scenario = config.get("character_scenario", "")
        self.bot.personality_catchphrases = config.get("personality_catchphrases", "")
        self.bot.personality_age = config.get("personality_age", "")
        self.bot.personality_likes = config.get("personality_likes", "")
        self.bot.personality_dislikes = config.get("personality_dislikes", "")
        self.bot.personality_goals = config.get("personality_goals", "")
        self.bot.personality_traits = config.get("personality_traits", "")
        self.bot.personality_physical_traits = config.get("personality_physical_traits", "")
        self.bot.personality_tone = config.get("personality_tone", "")
        self.bot.personality_history = config.get("personality_history", "")
        self.bot.personality_conversational_goals = config.get("personality_conversational_goals", "")
        self.bot.personality_conversational_examples = config.get("personality_conversational_examples", "")
        self.bot.free_will = config.get("free_will", False)
        self.bot.free_will_instruction = config.get("free_will_instruction", "")
        self.bot.jailbreak = config.get("jailbreak", "")
        
        # Behavior settings
        self.bot.add_character_name = config.get("add_character_name", True)
        self.bot.always_reply_mentions = config.get("always_reply_mentions", True)
        self.bot.reply_to_name = config.get("reply_to_name", True)
        self.bot.activated_channels = set(config.get("activated_channels", []))
        self.bot.use_tts = config.get("use_tts", False)
        
        # Moderation settings
        self.bot.blacklisted_users = config.get("blacklisted_users", [])
        self.bot.blacklisted_roles = config.get("blacklisted_roles", [])
        self.bot.conversation_timeout = config.get("conversation_timeout", 30)
        
        # API settings
        self.bot.api_settings = config.get("api_settings", {})
        self.bot.base_url = self.bot.api_settings.get("base_url", "")
        self.bot.api_key = self.bot.api_settings.get("api_key", "")
        self.bot.chat_model = self.bot.api_settings.get("chat_model", "")
        self.bot.tts_model = self.bot.api_settings.get("tts_model", "")
        self.bot.tts_voice = self.bot.api_settings.get("tts_voice", "")
        
        # Keep allowed_guilds if it exists
        if "allowed_guilds" in config:
            self.bot.allowed_guilds = config["allowed_guilds"]
            
    def update_field(self, field: str, value: Any) -> bool:
        """Update a specific configuration field and save"""
        try:
            # Load current config
            config = self.load_config()
            
            # Handle nested fields (e.g., api_settings.base_url)
            if "." in field:
                parts = field.split(".")
                if len(parts) == 2:
                    parent, child = parts
                    if parent in config and isinstance(config[parent], dict):
                        config[parent][child] = value
                    else:
                        config[parent] = {child: value}
            else:
                # Direct field update
                config[field] = value
                
            # Save config
            self.save_config(config)
            
            # Update the bot with new config
            self.update_bot_from_config(config)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating configuration field {field}: {str(e)}")
            return False
            
    def get_field(self, field: str) -> Any:
        """Get a specific configuration field value"""
        config = self.load_config()
        
        # Handle nested fields
        if "." in field:
            parts = field.split(".")
            if len(parts) == 2:
                parent, child = parts
                if parent in config and isinstance(config[parent], dict):
                    return config[parent].get(child)
                return None
        
        # Direct field access
        return config.get(field)


# Utility function to initialize config manager
def setup_config_manager(bot, config_path):
    config_manager = ConfigManager(bot, config_path)
    config = config_manager.load_config()
    config_manager.update_bot_from_config(config)
    return config_manager