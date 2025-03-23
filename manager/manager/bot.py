import discord
import asyncio
import os
import json
import nest_asyncio
from typing import Dict, Tuple, Any
from discord.ext import commands, tasks
from .utils import LoggerManager, DirectoryManager, ConfigManager, BotUtils
from .container import ContainerManager

nest_asyncio.apply()

BOT_CONFIG_FILE = "manager_config.json"
DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))

class OpenShapesManager(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

        self.logger = LoggerManager.setup()
        self.config_manager = ConfigManager(self.logger)
        self.config = self._load_config()
        self.container_manager = ContainerManager(self.logger, self.config)

        if self.config:
            DirectoryManager.create_required_directories(self.config["data_dir"])

        self.bg_tasks = []
        self.monitor_task = asyncio.run(self._create_monitor_task())

    @property
    def active_bots(self):
        if not hasattr(self, 'container_manager') or self.container_manager is None:
            self.logger.warning("Container manager not initialized, returning empty dict for active_bots")
            return {}
        return self.container_manager.active_bots

    def _load_config(self) -> dict:
        config_path = os.path.join(DIR, BOT_CONFIG_FILE)

        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        config = self.config_manager.load(config_path)
        if config:
            return config

        default_config = {
            "data_dir": "data",
            "max_bots_per_user": 5,
            "admin_users": [],
            "admin_roles": [],
            "docker_base_image": "openshapes:latest"
        }
        
        self.logger.warning("No configuration found, using default settings")

        try:
            ConfigManager.save(default_config, config_path)
            self.logger.info(f"Created default configuration file at {BOT_CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"Failed to save default configuration: {e}")
        
        return default_config
        
    def save_config(self) -> None:
        ConfigManager.save(self.config, os.path.join(DIR, BOT_CONFIG_FILE))
    
    async def register_cogs(self) -> None:
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        for file in os.listdir(cogs_dir):
            if file.endswith(".py") and not file.startswith("__"):
                await self.load_extension(f"manager.cogs.{file[:-3]}")

    async def setup_hook(self):
        await self.register_cogs()
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
        
        if self.config is None or "admin_users" not in self.config:
            self.logger.warning("Config missing or admin_users not found in config")
            return False
        
        if user_id in self.config.get("admin_users", []):
            return True

        if interaction.guild and "admin_roles" in self.config:
            user_roles = [str(role.id) for role in interaction.user.roles]
            for role_id in self.config.get("admin_roles", []):
                if role_id in user_roles:
                    return True
        return False

    def get_user_bots(self, user_id: str):
        return self.container_manager.get_user_bots(user_id)

    def get_user_bot_count(self, user_id: str) -> int:
        return self.container_manager.get_user_bot_count(user_id)

    def get_user_data_dir(self, user_id: str) -> str:
        return DirectoryManager.get_user_data_dir(self.config["data_dir"], user_id)

    def get_bot_config_dir(self, user_id: str, bot_name: str) -> str:
        return DirectoryManager.get_bot_config_dir(self.config["data_dir"], user_id, bot_name)

    async def create_bot(
        self,
        user_id: str,
        bot_name: str,
        config_json: Dict[str, Any],
        bot_token: str,
        brain_json: Dict[str, Any] = None
    ) -> Tuple[bool, str]:
        try:
            if not BotUtils.is_valid_bot_name(bot_name):
                return False, "Bot name must contain only letters, numbers, and underscores"

            user_bots = self.get_user_bots(user_id)
            if bot_name in user_bots:
                return False, f"You already have a bot named {bot_name}"

            is_admin = str(user_id) in self.config["admin_users"]
            if not is_admin and self.get_user_bot_count(user_id) >= self.config["max_bots_per_user"]:
                return False, f"You have reached the maximum limit of {self.config['max_bots_per_user']} bots"

            try:
                config_data = json.loads(config_json)
            except json.JSONDecodeError:
                return False, "Invalid JSON in config.json"

            brain_data = None
            if brain_json:
                try:
                    brain_data = json.loads(brain_json)
                except json.JSONDecodeError:
                    return False, "Invalid JSON in brain.json"

            bot_dir = self.get_bot_config_dir(user_id, bot_name)

            with open(os.path.join(bot_dir, "config.json"), "w") as f:
                json.dump(config_data, f, indent=2)

            if brain_data:
                with open(os.path.join(bot_dir, "brain.json"), "w") as f:
                    json.dump(brain_data, f, indent=2)

            parser_source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "parser.py")
            if not os.path.exists(parser_source):
                current_dir = os.getcwd()
                parser_source = os.path.join(current_dir, "scripts", "parser.py")

            parser_result = await self.container_manager.run_parser_container(bot_dir, parser_source)
            if not parser_result[0]:
                return parser_result

            try:
                config_path = os.path.join(bot_dir, "character_config.json")
                with open(config_path, "r") as f:
                    char_config = json.load(f)

                char_config["bot_token"] = bot_token
                char_config["owner_id"] = user_id
                char_config["character_name"] = bot_name

                with open(config_path, "w") as f:
                    json.dump(char_config, f, indent=2)
            except Exception as e:
                self.logger.error(f"Error updating character_config.json with token: {e}")
                return False, f"Error updating configuration: {str(e)}"

            container_result = await self.container_manager.start_bot_container(user_id, bot_name, bot_dir)
            if not container_result[0]:
                return container_result

            await self.container_manager.refresh_bot_list()
            return True, f"Bot {bot_name} created and started successfully"

        except Exception as e:
            self.logger.error(f"Error creating bot: {e}")
            return False, f"Error creating bot: {str(e)}"

    async def start_bot(self, user_id, bot_name):
        return await self.container_manager.start_bot(user_id, bot_name)

    async def stop_bot(self, user_id, bot_name):
        return await self.container_manager.stop_bot(user_id, bot_name)

    async def restart_bot(self, user_id, bot_name):
        return await self.container_manager.restart_bot(user_id, bot_name)

    async def delete_bot(self, user_id, bot_name):
        is_admin = str(user_id) in self.config["admin_users"]
        bot_dir = self.get_bot_config_dir(user_id, bot_name)
        return await self.container_manager.delete_bot(user_id, bot_name, is_admin, bot_dir)

    async def get_bot_logs(self, user_id, bot_name, lines=20):
        is_admin = str(user_id) in self.config["admin_users"]
        return await self.container_manager.get_bot_logs(user_id, bot_name, lines, is_admin)

    async def get_bot_stats(self, user_id, bot_name):
        return await self.container_manager.get_bot_stats(user_id, bot_name)