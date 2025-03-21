import logging
import os
import json
from typing import Dict, Optional, Any


class LoggingManager:
    def __init__(self, logger_name: str = "openshapes_manager", log_file: str = "openshapes_manager.log"):
        self.logger_name = logger_name
        self.log_file = log_file
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.logger = self._configure_logger()
    
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.logger_name)
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            file_handler = self._create_file_handler()
            console_handler = self._create_console_handler()
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        
        return logger
    
    def _create_file_handler(self) -> logging.FileHandler:
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(logging.Formatter(self.log_format))
        return file_handler
    
    def _create_console_handler(self) -> logging.StreamHandler:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(self.log_format))
        return console_handler
    
    def get_logger(self) -> logging.Logger:
        return self.logger


class DirectoryManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
    
    def create_required_directories(self) -> None:
        self._create_directory(self.base_dir)
        self._create_directory(os.path.join(self.base_dir, "users"))
        self._create_directory(os.path.join(self.base_dir, "configs"))
        self._create_directory(os.path.join(self.base_dir, "logs"))
    
    def _create_directory(self, directory_path: str) -> None:
        os.makedirs(directory_path, exist_ok=True)
    
    def get_user_data_dir(self, user_id: str) -> str:
        user_dir = os.path.join(self.base_dir, "users", user_id)
        self._create_directory(user_dir)
        return user_dir
    
    def get_bot_config_dir(self, user_id: str, bot_name: str) -> str:
        config_dir = os.path.join(self.get_user_data_dir(user_id), bot_name)
        self._create_directory(config_dir)
        return config_dir
    
    def get_bot_log_file(self, user_id: str, bot_name: str) -> str:
        log_dir = os.path.join(self.base_dir, "logs")
        self._create_directory(log_dir)
        return os.path.join(log_dir, f"{user_id}_{bot_name}.log")


class ConfigurationManager:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def load_config(self, config_file: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(config_file):
            self.logger.warning(f"Config file not found: {config_file}")
            return None
        
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON format in config file {config_file}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error loading config from {config_file}: {e}")
            return None
    
    def save_config(self, config: Dict[str, Any], config_file: str) -> bool:
        try:
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving config to {config_file}: {e}")
            return False


class ValidationUtils:
    @staticmethod
    def is_valid_bot_name(bot_name: str) -> bool:
        return bot_name.replace("_", "").isalnum()
    
    @staticmethod
    def is_valid_user_id(user_id: str) -> bool:
        return user_id.isdigit()
    
    @staticmethod
    def is_valid_json(json_string: str) -> bool:
        try:
            json.loads(json_string)
            return True
        except json.JSONDecodeError:
            return False


def setup_logger() -> logging.Logger:
    logging_manager = LoggingManager()
    return logging_manager.get_logger()


def create_required_directories(data_dir: str) -> None:
    directory_manager = DirectoryManager(data_dir)
    directory_manager.create_required_directories()


def load_config(config_file: str) -> Optional[Dict[str, Any]]:
    logger = setup_logger()
    config_manager = ConfigurationManager(logger)
    return config_manager.load_config(config_file)


def save_config(config: Dict[str, Any], config_file: str) -> bool:
    logger = setup_logger()
    config_manager = ConfigurationManager(logger)
    return config_manager.save_config(config, config_file)


def get_user_data_dir(base_dir: str, user_id: str) -> str:
    directory_manager = DirectoryManager(base_dir)
    return directory_manager.get_user_data_dir(user_id)


def get_bot_config_dir(base_dir: str, user_id: str, bot_name: str) -> str:
    directory_manager = DirectoryManager(base_dir)
    return directory_manager.get_bot_config_dir(user_id, bot_name)


def get_bot_log_file(base_dir: str, user_id: str, bot_name: str) -> str:
    directory_manager = DirectoryManager(base_dir)
    return directory_manager.get_bot_log_file(user_id, bot_name)


def is_valid_bot_name(bot_name: str) -> bool:
    return ValidationUtils.is_valid_bot_name(bot_name)
