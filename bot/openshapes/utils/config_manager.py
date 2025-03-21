import json
import logging
import os
from typing import Any

logger = logging.getLogger("openshape")

class ConfigManager:
    def __init__(self, bot, config_path: str):
        self.bot = bot
        self.config_path = config_path
    
    def save_config(self) -> bool:
        try:
            config = self.bot.character_config.copy()

            config["character_name"] = self.bot.character_name
            config["system_prompt"] = self.bot.system_prompt
            config["character_backstory"] = self.bot.character_backstory
            config["character_description"] = self.bot.character_description
            config["character_scenario"] = self.bot.character_scenario
            config["personality_catchphrases"] = self.bot.personality_catchphrases
            config["personality_age"] = self.bot.personality_age
            config["personality_likes"] = self.bot.personality_likes
            config["personality_dislikes"] = self.bot.personality_dislikes
            config["personality_goals"] = self.bot.personality_goals
            config["personality_traits"] = self.bot.personality_traits
            config["personality_physical_traits"] = self.bot.personality_physical_traits
            config["personality_tone"] = self.bot.personality_tone
            config["personality_history"] = self.bot.personality_history
            config["personality_conversational_goals"] = self.bot.personality_conversational_goals
            config["personality_conversational_examples"] = self.bot.personality_conversational_examples
            config["free_will"] = self.bot.free_will
            config["free_will_instruction"] = self.bot.free_will_instruction
            config["jailbreak"] = self.bot.jailbreak

            config["add_character_name"] = self.bot.add_character_name
            config["reply_to_name"] = self.bot.reply_to_name
            config["always_reply_mentions"] = self.bot.always_reply_mentions
            config["use_tts"] = self.bot.use_tts

            config["activated_channels"] = list(self.bot.activated_channels)
            config["blacklisted_users"] = self.bot.blacklisted_users
            config["blacklisted_roles"] = self.bot.blacklisted_roles

            config["api_settings"] = {
                "base_url": self.bot.base_url,
                "api_key": self.bot.api_key,
                "chat_model": self.bot.chat_model,
                "tts_model": self.bot.tts_model,
                "tts_voice": self.bot.tts_voice
            }

            if os.path.exists(self.config_path):
                backup_path = f"{self.config_path}.bak"
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        current_config = f.read()
                    
                    with open(backup_path, 'w', encoding='utf-8') as f:
                        f.write(current_config)
                except Exception as e:
                    logger.error(f"Failed to create config backup: {e}")

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"Configuration saved to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def update_field(self, field_name: str, value: Any) -> bool:
        try:
            if hasattr(self.bot, field_name):
                setattr(self.bot, field_name, value)

            if '.' in field_name:
                parts = field_name.split('.')
                if len(parts) == 2:
                    parent, child = parts
                    if parent == "api_settings":
                        self.bot.api_settings[child] = value

                        if child == "base_url":
                            self.bot.base_url = value
                        elif child == "api_key":
                            self.bot.api_key = value
                        elif child == "chat_model":
                            self.bot.chat_model = value
                        elif child == "tts_model":
                            self.bot.tts_model = value
                        elif child == "tts_voice":
                            self.bot.tts_voice = value

            return self.save_config()
        except Exception as e:
            logger.error(f"Failed to update field {field_name}: {e}")
            return False
