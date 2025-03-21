import logging
import os
import json
from typing import Dict

def setup_logger():
    logger = logging.getLogger("openshapes_manager")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        file_handler = logging.FileHandler("openshapes_manager.log")
        console_handler = logging.StreamHandler()
        
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

def create_required_directories(data_dir: str):
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, "users"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "configs"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "logs"), exist_ok=True)

def load_config(config_file: str) -> Dict:
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger = setup_logger()
            logger.error(f"Error loading config: {e}")
    
    return None

def save_config(config: Dict, config_file: str) -> None:
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

def get_user_data_dir(base_dir: str, user_id: str) -> str:
    user_dir = os.path.join(base_dir, "users", user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_bot_config_dir(base_dir: str, user_id: str, bot_name: str) -> str:
    config_dir = os.path.join(get_user_data_dir(base_dir, user_id), bot_name)
    os.makedirs(config_dir, exist_ok=True)
    return config_dir

def get_bot_log_file(base_dir: str, user_id: str, bot_name: str) -> str:
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, f"{user_id}_{bot_name}.log")

def is_valid_bot_name(bot_name: str) -> bool:
    return bot_name.replace("_", "").isalnum()
