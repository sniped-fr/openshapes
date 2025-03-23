import json
import logging
import os
import traceback
from typing import Any, Dict, Optional, TypeVar, Generic, Callable

logger = logging.getLogger("openshape")

T = TypeVar('T')

class ConfigField(Generic[T]):
    def __init__(self, path: str, default: Optional[T] = None):
        self.path = path
        self.default = default

class ConfigBackupManager:
    def __init__(self, config_path: str, max_backups: int = 5):
        self.config_path = config_path
        self.max_backups = max_backups
        
    def create_backup(self) -> Optional[str]:
        if not os.path.exists(self.config_path):
            return None
            
        try:
            backup_path = f"{self.config_path}.bak"
            with open(self.config_path, 'r', encoding='utf-8') as f:
                current_config = f.read()
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(current_config)
                
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create config backup: {e}")
            return None
            
    def rotate_backups(self) -> None:
        backup_dir = os.path.dirname(self.config_path)

        if not os.path.exists(backup_dir):
            os.mkdir(backup_dir)

        base_name = os.path.basename(self.config_path)
        backup_files = [
            f for f in os.listdir(backup_dir)
            if f.startswith(f"{base_name}.bak")
        ]
        
        if len(backup_files) > self.max_backups:
            backup_files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)))
            for old_backup in backup_files[:(len(backup_files) - self.max_backups)]:
                try:
                    os.remove(os.path.join(backup_dir, old_backup))
                except Exception as e:
                    logger.error(f"Failed to remove old backup {old_backup}: {e}")

class ConfigMapper:
    @staticmethod
    def extract_personality_config(bot) -> Dict[str, Any]:
        return {
            "character_name": bot.character_name,
            "system_prompt": bot.system_prompt,
            "character_backstory": bot.character_backstory,
            "character_description": bot.character_description,
            "character_scenario": bot.character_scenario,
            "personality_catchphrases": bot.personality_catchphrases,
            "personality_age": bot.personality_age,
            "personality_likes": bot.personality_likes,
            "personality_dislikes": bot.personality_dislikes,
            "personality_goals": bot.personality_goals,
            "personality_traits": bot.personality_traits,
            "personality_physical_traits": bot.personality_physical_traits,
            "personality_tone": bot.personality_tone,
            "personality_history": bot.personality_history,
            "personality_conversational_goals": bot.personality_conversational_goals,
            "personality_conversational_examples": bot.personality_conversational_examples,
            "free_will": bot.free_will,
            "free_will_instruction": bot.free_will_instruction,
            "jailbreak": bot.jailbreak
        }
        
    @staticmethod
    def extract_behavior_config(bot) -> Dict[str, Any]:
        return {
            "add_character_name": bot.add_character_name,
            "reply_to_name": bot.reply_to_name,
            "always_reply_mentions": bot.always_reply_mentions,
            "use_tts": bot.use_tts,
            "activated_channels": list(bot.activated_channels),
            "blacklisted_users": bot.blacklisted_users,
            "blacklisted_roles": bot.blacklisted_roles
        }
        
    @staticmethod
    def extract_api_config(bot) -> Dict[str, Any]:
        return {
            "base_url": bot.api_integration.base_url,
            "api_key": bot.api_integration.api_key,
            "chat_model": bot.api_integration.chat_model,
            "tts_model": bot.api_integration.tts_model,
            "tts_voice": bot.api_integration.tts_voice
        }

class ConfigSerializer:
    @staticmethod
    def serialize(config: Dict[str, Any], path: str) -> bool:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to serialize config to {path}: {e}")
            return False
            
    @staticmethod
    def deserialize(path: str) -> Optional[Dict[str, Any]]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to deserialize config from {path}: {e}")
            return None

class ConfigManager:
    def __init__(self, bot):
        self.bot = bot
        self.backup_manager = ConfigBackupManager(self.bot.config_path)
        self.field_mapping = self._initialize_field_mapping()
    
    def _initialize_field_mapping(self) -> Dict[str, Callable[[Any], None]]:
        api_settings_fields = {
            "base_url": lambda v: setattr(self.bot.api_integration, "base_url", v),
            "api_key": lambda v: setattr(self.bot.api_integration, "api_key", v),
            "chat_model": lambda v: setattr(self.bot.api_integration, "chat_model", v),
            "tts_model": lambda v: setattr(self.bot.api_integration, "tts_model", v),
            "tts_voice": lambda v: setattr(self.bot.api_integration, "tts_voice", v)
        }
        
        return {
            "api_settings": lambda v: self._update_nested_field("api_settings", v, api_settings_fields)
        }
    
    def _update_nested_field(
        self,
        parent_field: str,
        value: Dict[str, Any],
        field_mapping: Dict[str, Callable[[Any], None]]
    ) -> None:
        if hasattr(self.bot, parent_field) and isinstance(value, dict):
            parent_obj = getattr(self.bot, parent_field)
            for key, val in value.items():
                if key in parent_obj and key in field_mapping:
                    parent_obj[key] = val
                    field_mapping[key](val)
    
    def save_config(self) -> bool:
        try:
            config = self.bot.config_manager.data.copy()

            config.update(ConfigMapper.extract_personality_config(self.bot))
            config.update(ConfigMapper.extract_behavior_config(self.bot))
            config["api_settings"] = ConfigMapper.extract_api_config(self.bot)

            self.backup_manager.create_backup()
            self.backup_manager.rotate_backups()

            if ConfigSerializer.serialize(config, self.bot.config_path):
                logger.info(f"Configuration saved to {self.bot.config_path}")
                return True
            return False
            
        except Exception:
            logger.error(f"Failed to save configuration: {traceback.format_exc()}")
            return False
    
    def update_field(self, field_name: str, value: Any) -> bool:
        try:
            if hasattr(self.bot, field_name):
                setattr(self.bot, field_name, value)
                return self.save_config()

            if field_name in self.field_mapping:
                self.field_mapping[field_name](value)
                return self.save_config()

            if '.' in field_name:
                parts = field_name.split('.')
                if len(parts) == 2:
                    parent, child = parts
                    if parent == "api_settings":
                        if hasattr(self.bot.api_integration, child):
                            setattr(self.bot.api_integration, child, value)
                            return self.save_config()
                            
            logger.warning(f"Field {field_name} not found")
            return False
        except Exception as e:
            logger.error(f"Failed to update field {field_name}: {e}")
            return False
