import logging
import os
import json
from typing import Dict, Optional

class LoggerManager:
    @staticmethod
    def setup() -> logging.Logger:
        logger = logging.getLogger("manager")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        return logger

class DirectoryManager:
    @staticmethod
    def create_required_directories(data_dir: str) -> None:
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(os.path.join(data_dir, "users"), exist_ok=True)
        os.makedirs(os.path.join(data_dir, "configs"), exist_ok=True)
    
    @staticmethod
    def get_user_data_dir(base_dir: str, user_id: str) -> str:
        user_dir = os.path.join(base_dir, "users", user_id)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir
    
    @staticmethod
    def get_bot_config_dir(base_dir: str, user_id: str, bot_name: str) -> str:
        config_dir = os.path.join(DirectoryManager.get_user_data_dir(base_dir, user_id), bot_name)
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

class ConfigManager:
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or LoggerManager.setup()
    
    def load(self, config_file: str) -> Optional[Dict]:
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading config: {e}")
        return None
    
    @staticmethod
    def save(config: Dict, config_file: str) -> None:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

class BotUtils:
    @staticmethod
    def is_valid_bot_name(bot_name: str) -> bool:
        return bot_name.replace("_", "").isalnum()