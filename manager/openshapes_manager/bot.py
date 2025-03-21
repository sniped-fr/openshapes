import discord
from discord.ext import commands, tasks
import asyncio
import os
import json
import nest_asyncio
import dotenv

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

class OpenShapesManager(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

        self.logger = setup_logger()
        self.config = self._load_config()
        print(self.config)
        self.container_manager = ContainerManager(self.logger, self.config)
        
        # Add this property to ensure backward compatibility
        # This property delegates to container_manager's active_bots
        # So any code that relies on self.active_bots will still work
        
        if self.config:
            create_required_directories(self.config["data_dir"])

        self.bg_tasks = []
        self.monitor_task = asyncio.run(self._create_monitor_task())

    # Property to delegate active_bots access to container_manager
    @property
    def active_bots(self):
        return self.container_manager.active_bots

    def _load_config(self) -> dict:
        if os.path.exists(BOT_CONFIG_FILE):
            try:
                with open(BOT_CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading config: {e}")
        return None

    def save_config(self) -> None:
        with open(BOT_CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

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

        if user_id in self.config["admin_users"]:
            return True

        if interaction.guild:
            user_roles = [str(role.id) for role in interaction.user.roles]
            for role_id in self.config["admin_roles"]:
                if role_id in user_roles:
                    return True

        return False

    def get_user_bots(self, user_id: str):
        return self.container_manager.get_user_bots(user_id)

    def get_user_bot_count(self, user_id: str) -> int:
        return self.container_manager.get_user_bot_count(user_id)

    def get_user_data_dir(self, user_id: str) -> str:
        user_dir = os.path.join(self.config["data_dir"], "users", user_id)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def get_bot_config_dir(self, user_id: str, bot_name: str) -> str:
        config_dir = os.path.join(self.get_user_data_dir(user_id), bot_name)
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def get_bot_log_file(self, user_id: str, bot_name: str) -> str:
        log_dir = os.path.join(self.config["data_dir"], "logs")
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, f"{user_id}_{bot_name}.log")

    async def create_bot(self, user_id, bot_name, config_json, bot_token, brain_json=None):
        try:
            if not bot_name.replace("_", "").isalnum():
                return (
                    False,
                    "Bot name must contain only letters, numbers, and underscores",
                )

            user_bots = self.get_user_bots(user_id)
            if bot_name in user_bots:
                return False, f"You already have a bot named {bot_name}"

            is_admin = str(user_id) in self.config["admin_users"]
            if (
                not is_admin
                and self.get_user_bot_count(user_id) >= self.config["max_bots_per_user"]
            ):
                return (
                    False,
                    f"You have reached the maximum limit of {self.config['max_bots_per_user']} bots",
                )

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

            # Get parser source from scripts directory
            parser_source = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "parser.py"
            )

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

                with open(config_path, "w") as f:
                    json.dump(char_config, f, indent=2)
            except Exception as e:
                self.logger.error(f"Error updating character_config.json with token: {e}")
                return False, f"Error updating configuration: {str(e)}"

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


def main():
    bot = OpenShapesManager()
    token = os.environ.get("token")

    if token == "YOUR_DISCORD_BOT_TOKEN":
        print("Please set your bot token in manager_config.json")
        return

    bot.run(token)


if __name__ == "__main__":
    main()