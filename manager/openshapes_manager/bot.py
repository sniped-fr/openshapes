import discord
import asyncio
import os
import json
import nest_asyncio
import dotenv
from typing import Dict, Tuple, Any, Optional
from discord.ext import commands, tasks

try:
    from .utils import setup_logger, create_required_directories
    from .container import ContainerManager
    from .commands import setup_commands
except ImportError:
    from utils import setup_logger, create_required_directories
    from container import ContainerManager
    from commands import setup_commands

nest_asyncio.apply()
dotenv.load_dotenv()

BOT_CONFIG_FILE = "manager_config.json"


class ConfigManager:
    def __init__(self, logger):
        self.logger = logger
        self.config_file = BOT_CONFIG_FILE
        self.config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    self.config = json.load(f)
                return self.config
            except Exception as e:
                self.logger.error(f"Error loading config: {e}")
        return {}
    
    def save(self) -> None:
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self.config[key] = value


class PathManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
    
    def get_user_data_dir(self, user_id: str) -> str:
        user_dir = os.path.join(self.data_dir, "users", user_id)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir
    
    def get_bot_config_dir(self, user_id: str, bot_name: str) -> str:
        config_dir = os.path.join(self.get_user_data_dir(user_id), bot_name)
        os.makedirs(config_dir, exist_ok=True)
        return config_dir
    
    def get_bot_log_file(self, user_id: str, bot_name: str) -> str:
        log_dir = os.path.join(self.data_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, f"{user_id}_{bot_name}.log")
    
    def get_parser_path(self) -> str:
        parser_source = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "parser.py"
        )
        
        if not os.path.exists(parser_source):
            current_dir = os.getcwd()
            parser_source = os.path.join(current_dir, "scripts", "parser.py")
            
        return parser_source


class BotValidator:
    @staticmethod
    def validate_bot_name(bot_name: str) -> Tuple[bool, str]:
        if not bot_name.replace("_", "").isalnum():
            return False, "Bot name must contain only letters, numbers, and underscores"
        return True, ""
    
    @staticmethod
    def validate_json(json_str: str) -> Tuple[bool, Any]:
        try:
            data = json.loads(json_str)
            return True, data
        except json.JSONDecodeError:
            return False, "Invalid JSON format"


class BotCreateProcessor:
    def __init__(self, manager, logger, path_manager, container_manager):
        self.manager = manager
        self.logger = logger
        self.path_manager = path_manager
        self.container_manager = container_manager
        self.validator = BotValidator()
    
    async def process(
        self, 
        user_id: str, 
        bot_name: str, 
        config_json: str, 
        bot_token: str, 
        brain_json: Optional[str] = None
    ) -> Tuple[bool, str]:
        try:
            name_valid, error_msg = self.validator.validate_bot_name(bot_name)
            if not name_valid:
                return False, error_msg
            
            user_bots = self.container_manager.get_user_bots(user_id)
            if bot_name in user_bots:
                return False, f"You already have a bot named {bot_name}"
            
            if not self._check_user_bot_limits(user_id):
                max_bots = self.manager.config_manager.get("max_bots_per_user", 5)
                return False, f"You have reached the maximum limit of {max_bots} bots"
            
            valid_config, config_data = self.validator.validate_json(config_json)
            if not valid_config:
                return False, "Invalid JSON in config.json"
            
            brain_data = None
            if brain_json:
                valid_brain, brain_result = self.validator.validate_json(brain_json)
                if not valid_brain:
                    return False, "Invalid JSON in brain.json"
                brain_data = brain_result
            
            bot_dir = self.path_manager.get_bot_config_dir(user_id, bot_name)
            self._save_config_files(bot_dir, config_data, brain_data)
            
            parser_source = self.path_manager.get_parser_path()
            parser_result = await self.container_manager.run_parser_container(bot_dir, parser_source)
            if not parser_result[0]:
                return parser_result
            
            token_update_result = self._update_bot_token(bot_dir, bot_token)
            if not token_update_result[0]:
                return token_update_result
            
            container_result = await self.container_manager.start_bot_container(
                user_id, bot_name, bot_dir
            )
            if not container_result[0]:
                return container_result
            
            await self.container_manager.refresh_bot_list()
            
            return True, f"Bot {bot_name} created and started successfully"
            
        except Exception as e:
            self.logger.error(f"Error creating bot: {e}")
            return False, f"Error creating bot: {str(e)}"
    
    def _check_user_bot_limits(self, user_id: str) -> bool:
        is_admin = str(user_id) in self.manager.config_manager.get("admin_users", [])
        if is_admin:
            return True
            
        max_bots = self.manager.config_manager.get("max_bots_per_user", 5)
        user_bot_count = self.container_manager.get_user_bot_count(user_id)
        return user_bot_count < max_bots
    
    def _save_config_files(
        self, 
        bot_dir: str, 
        config_data: Dict[str, Any], 
        brain_data: Optional[Dict[str, Any]] = None
    ) -> None:
        with open(os.path.join(bot_dir, "config.json"), "w") as f:
            json.dump(config_data, f, indent=2)
        
        if brain_data:
            with open(os.path.join(bot_dir, "brain.json"), "w") as f:
                json.dump(brain_data, f, indent=2)
    
    def _update_bot_token(self, bot_dir: str, bot_token: str) -> Tuple[bool, str]:
        try:
            config_path = os.path.join(bot_dir, "character_config.json")
            with open(config_path, "r") as f:
                char_config = json.load(f)
            
            char_config["bot_token"] = bot_token
            
            with open(config_path, "w") as f:
                json.dump(char_config, f, indent=2)
                
            return True, "Bot token updated successfully"
        except Exception as e:
            self.logger.error(f"Error updating character_config.json with token: {e}")
            return False, f"Error updating configuration: {str(e)}"


class OpenShapesManager(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        
        self.logger = setup_logger()
        self.config_manager = ConfigManager(self.logger)
        
        if self.config_manager.config:
            data_dir = self.config_manager.get("data_dir", "data")
            create_required_directories(data_dir)
            self.path_manager = PathManager(data_dir)
            self.container_manager = ContainerManager(self.logger, self.config_manager.config)
            self.bot_creator = BotCreateProcessor(
                self, self.logger, self.path_manager, self.container_manager
            )
            
            self.bg_tasks = []
            self.monitor_task = asyncio.run(self._create_monitor_task())
    
    def save_config(self) -> None:
        self.config_manager.save()

    async def setup_hook(self):
        create_commands, manage_commands, admin_commands, tutorial_commands = setup_commands(self)
        
        self.tree.add_command(create_commands)
        self.tree.add_command(manage_commands)
        self.tree.add_command(admin_commands)
        self.tree.add_command(tutorial_commands)
        
        try:
            await self.tree.sync()
            self.logger.info("Commands registered and synced with Discord")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        self.logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        self.logger.info(f"Discord.py version: {discord.__version__}")
        self.logger.info("Bot is ready")

    async def _create_monitor_task(self):
        @tasks.loop(minutes=5)
        async def monitor_containers_task():
            await self.container_manager.refresh_bot_list()
            self.logger.info("Container monitor: Refreshed bot list")
        
        monitor_task = monitor_containers_task
        monitor_task.start()
        
        await self.container_manager.refresh_bot_list()
        return monitor_task

    async def refresh_bot_list(self):
        await self.container_manager.refresh_bot_list()

    def is_admin(self, interaction: discord.Interaction) -> bool:
        user_id = str(interaction.user.id)
        
        if user_id in self.config_manager.get("admin_users", []):
            return True
        
        if interaction.guild:
            user_roles = [str(role.id) for role in interaction.user.roles]
            for role_id in self.config_manager.get("admin_roles", []):
                if role_id in user_roles:
                    return True
        
        return False

    def get_user_bots(self, user_id: str) -> Dict[str, Any]:
        return self.container_manager.get_user_bots(user_id)

    def get_user_bot_count(self, user_id: str) -> int:
        return self.container_manager.get_user_bot_count(user_id)

    def get_user_data_dir(self, user_id: str) -> str:
        return self.path_manager.get_user_data_dir(user_id)

    def get_bot_config_dir(self, user_id: str, bot_name: str) -> str:
        return self.path_manager.get_bot_config_dir(user_id, bot_name)

    def get_bot_log_file(self, user_id: str, bot_name: str) -> str:
        return self.path_manager.get_bot_log_file(user_id, bot_name)

    async def create_bot(
        self, 
        user_id: str, 
        bot_name: str, 
        config_json: str, 
        bot_token: str, 
        brain_json: Optional[str] = None
    ) -> Tuple[bool, str]:
        return await self.bot_creator.process(user_id, bot_name, config_json, bot_token, brain_json)

    async def start_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        return await self.container_manager.start_bot(user_id, bot_name)

    async def stop_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        return await self.container_manager.stop_bot(user_id, bot_name)

    async def restart_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        return await self.container_manager.restart_bot(user_id, bot_name)

    async def delete_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        is_admin = str(user_id) in self.config_manager.get("admin_users", [])
        bot_dir = self.path_manager.get_bot_config_dir(user_id, bot_name)
        return await self.container_manager.delete_bot(user_id, bot_name, is_admin, bot_dir)

    async def get_bot_logs(
        self, user_id: str, bot_name: str, lines: int = 20
    ) -> Tuple[bool, str]:
        is_admin = str(user_id) in self.config_manager.get("admin_users", [])
        return await self.container_manager.get_bot_logs(user_id, bot_name, lines, is_admin)

    async def get_bot_stats(self, user_id: str, bot_name: str) -> Tuple[bool, Dict[str, Any]]:
        return await self.container_manager.get_bot_stats(user_id, bot_name)


class BotApplication:
    def __init__(self):
        self.bot = OpenShapesManager()
    
    def run(self) -> None:
        token = os.environ.get("token")
        
        if not token or token == "YOUR_DISCORD_BOT_TOKEN":
            print("Please set your bot token in manager_config.json")
            return
        
        self.bot.run(token)


def main() -> None:
    app = BotApplication()
    app.run()


if __name__ == "__main__":
    main()
