import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import logging
import json
import os
import docker
import tempfile
import time
from typing import Dict, List, Optional, Tuple, Any
import nest_asyncio

nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("openshapes_manager.log"), logging.StreamHandler()],
)
logger = logging.getLogger("openshapes_manager")

# Bot configuration
BOT_CONFIG_FILE = "manager_config.json"

# Define command groups
create_commands = app_commands.Group(
    name="create", description="Create a new OpenShapes bot"
)

manage_commands = app_commands.Group(
    name="manage", description="Manage your OpenShapes bots"
)

admin_commands = app_commands.Group(
    name="admin", description="Admin commands for bot management"
)

tutorial_commands = app_commands.Group(
    name="tutorial", description="Get help with OpenShapes setup"
)


class OpenShapesManager(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

        # Load configuration
        self.config = self.load_config()

        # Initialize Discord client
        self.docker_client = docker.from_env()

        # Dictionary to track running bots
        self.active_bots = {}

        # Create data directory if it doesn't exist
        os.makedirs(self.config["data_dir"], exist_ok=True)
        os.makedirs(os.path.join(self.config["data_dir"], "users"), exist_ok=True)
        os.makedirs(os.path.join(self.config["data_dir"], "configs"), exist_ok=True)
        os.makedirs(os.path.join(self.config["data_dir"], "logs"), exist_ok=True)

        # Set up background tasks
        self.bg_tasks = []

        # Setup container monitoring task
        self.monitor_containers = asyncio.run(self._create_monitor_task())

    def load_config(self) -> dict:
        """Load bot configuration from file or create default"""
        if os.path.exists(BOT_CONFIG_FILE):
            try:
                with open(BOT_CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    # Merge with defaults for any missing keys
                    return config
            except Exception as e:
                logger.error(f"Error loading config: {e}")

        return None

    def save_config(self) -> None:
        """Save current configuration to file"""
        with open(BOT_CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Add the command groups to the tree
        self.tree.add_command(create_commands)
        self.tree.add_command(manage_commands)
        self.tree.add_command(admin_commands)
        self.tree.add_command(tutorial_commands)

        # Register all commands
        self.setup_commands()

        # Sync the command tree with Discord
        try:
            # This will sync the commands to Discord
            await self.tree.sync()
            logger.info("Commands registered and synced with Discord")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    def setup_commands(self):
        """Setup all slash commands"""

        # Setup create commands
        @create_commands.command(name="bot", description="Create a new OpenShapes bot")
        async def create_bot_command(
            interaction: discord.Interaction,
            bot_name: str,
            bot_token: str,
            config_file: discord.Attachment,
            brain_file: Optional[discord.Attachment] = None,
        ):
            await interaction.response.defer(
                thinking=True, ephemeral=True
            )  # Making response ephemeral for token security
            user_id = str(interaction.user.id)

            try:
                # Download config file
                config_content = await config_file.read()
                config_json = config_content.decode("utf-8")

                # Download brain file if provided
                brain_json = None
                if brain_file:
                    brain_content = await brain_file.read()
                    brain_json = brain_content.decode("utf-8")

                # Create the bot
                success, message = await self.create_bot(
                    user_id, bot_name, config_json, bot_token, brain_json
                )

                if success:
                    await interaction.followup.send(f"✅ {message}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ {message}", ephemeral=True)

            except Exception as e:
                logger.error(f"Error in create_bot_command: {e}")
                await interaction.followup.send(
                    f"❌ An error occurred: {str(e)}", ephemeral=True
                )

        # Setup tutorial commands
        @tutorial_commands.command(
            name="token",
            description="Learn how to get a Discord bot token and enable intents",
        )
        async def token_tutorial_command(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)

            # Create an embed with the tutorial
            embed = discord.Embed(
                title="How to Get a Discord Bot Token and Enable Intents",
                description="This guide will walk you through creating a Discord bot application and getting your bot token.",
                color=discord.Color.blue(),
            )

            # Step 1
            embed.add_field(
                name="Step 1: Create a Discord Application",
                value="1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)\n"
                "2. Click the 'New Application' button\n"
                "3. Enter a name for your application and click 'Create'",
                inline=False,
            )

            # Step 2
            embed.add_field(
                name="Step 2: Create a Bot",
                value="1. In your application, go to the 'Bot' tab on the left sidebar\n"
                "2. Click 'Add Bot' and confirm by clicking 'Yes, do it!'",
                inline=False,
            )

            # Step 3
            embed.add_field(
                name="Step 3: Enable Intents",
                value="In the Bot tab, scroll down to 'Privileged Gateway Intents' and enable:\n"
                "• Presence Intent\n"
                "• Server Members Intent\n"
                "• Message Content Intent\n\n"
                "These are required for OpenShapes bots to function properly.",
                inline=False,
            )

            # Step 4
            embed.add_field(
                name="Step 4: Get Your Bot Token",
                value="1. In the Bot tab, click the 'Reset Token' button\n"
                "2. Confirm the action\n"
                "3. Copy your token (it will only be shown once!)\n\n"
                "⚠️ **IMPORTANT**: Keep your token secret! Anyone with your token can control your bot.",
                inline=False,
            )

            # Step 5
            embed.add_field(
                name="Step 5: Invite Your Bot to Servers",
                value="1. Go to the 'OAuth2' tab on the left sidebar\n"
                "2. Select 'URL Generator'\n"
                "3. In 'Scopes', select 'bot' and 'applications.commands'\n"
                "4. In 'Bot Permissions', select the permissions your bot needs\n"
                "5. Copy and open the generated URL to invite the bot to a server",
                inline=False,
            )

            # Step 6
            embed.add_field(
                name="Using Your Token with OpenShapes",
                value="Use the `/create bot` command and provide:\n"
                "• A name for your bot\n"
                "• Your bot token\n"
                "• Your config.json file\n"
                "• Optionally, a brain.json file\n\n"
                "The bot will be created with your token and started automatically.",
                inline=False,
            )

            await interaction.followup.send(embed=embed)

        # Setup manage commands
        @manage_commands.command(name="list", description="List your OpenShapes bots")
        async def list_bots_command(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            user_id = str(interaction.user.id)
            user_bots = self.get_user_bots(user_id)

            if not user_bots:
                await interaction.followup.send(
                    "You don't have any OpenShapes bots yet. Use `/create bot` to create one."
                )
                return

            # Create an embed to list the bots
            embed = discord.Embed(
                title="Your OpenShapes Bots",
                description=f"You have {len(user_bots)} bot(s)",
                color=discord.Color.blue(),
            )

            for name, bot_info in user_bots.items():
                status_emoji = "🟢" if bot_info["status"] == "running" else "🔴"
                embed.add_field(
                    name=f"{status_emoji} {name}",
                    value=f"Status: {bot_info['status']}\nID: {bot_info['container_id'][:12]}",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        @manage_commands.command(name="start", description="Start a stopped bot")
        async def start_bot_command(interaction: discord.Interaction, bot_name: str):
            await interaction.response.defer(thinking=True)
            user_id = str(interaction.user.id)
            success, message = await self.start_bot(user_id, bot_name)

            if success:
                await interaction.followup.send(f"✅ {message}")
            else:
                await interaction.followup.send(f"❌ {message}")

        @manage_commands.command(name="stop", description="Stop a running bot")
        async def stop_bot_command(interaction: discord.Interaction, bot_name: str):
            await interaction.response.defer(thinking=True)
            user_id = str(interaction.user.id)
            success, message = await self.stop_bot(user_id, bot_name)

            if success:
                await interaction.followup.send(f"✅ {message}")
            else:
                await interaction.followup.send(f"❌ {message}")

        @manage_commands.command(name="restart", description="Restart a bot")
        async def restart_bot_command(interaction: discord.Interaction, bot_name: str):
            await interaction.response.defer(thinking=True)
            user_id = str(interaction.user.id)
            success, message = await self.restart_bot(user_id, bot_name)

            if success:
                await interaction.followup.send(f"✅ {message}")
            else:
                await interaction.followup.send(f"❌ {message}")

        @manage_commands.command(name="delete", description="Delete a bot completely")
        async def delete_bot_command(interaction: discord.Interaction, bot_name: str):
            await interaction.response.defer(thinking=True)
            user_id = str(interaction.user.id)

            # Create a confirmation button
            confirm_view = discord.ui.View(timeout=60)
            confirm_button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Confirm Delete",
                custom_id="confirm_delete",
            )
            cancel_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Cancel",
                custom_id="cancel_delete",
            )

            async def confirm_callback(button_interaction: discord.Interaction):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message(
                        "This is not your confirmation dialog", ephemeral=True
                    )
                    return

                success, message = await self.delete_bot(user_id, bot_name)
                if success:
                    await button_interaction.response.edit_message(
                        content=f"✅ {message}", view=None
                    )
                else:
                    await button_interaction.response.edit_message(
                        content=f"❌ {message}", view=None
                    )

            async def cancel_callback(button_interaction: discord.Interaction):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message(
                        "This is not your confirmation dialog", ephemeral=True
                    )
                    return
                await button_interaction.response.edit_message(
                    content="Delete operation canceled", view=None
                )

            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)

            await interaction.followup.send(
                f"⚠️ Are you sure you want to delete the bot '{bot_name}'? This action cannot be undone.",
                view=confirm_view,
            )

        @manage_commands.command(name="logs", description="Get logs from a bot")
        async def logs_bot_command(
            interaction: discord.Interaction, bot_name: str, lines: int = 20
        ):
            await interaction.response.defer(thinking=True)
            user_id = str(interaction.user.id)
            success, logs = await self.get_bot_logs(user_id, bot_name, lines)

            if success:
                # Truncate logs if too long
                if len(logs) > 1950:
                    logs = logs[-1950:] + "...(truncated)"
                await interaction.followup.send(f"```\n{logs}\n```")
            else:
                await interaction.followup.send(f"❌ {logs}")

        @manage_commands.command(
            name="status", description="Get detailed status of a bot"
        )
        async def status_bot_command(interaction: discord.Interaction, bot_name: str):
            await interaction.response.defer(thinking=True)
            user_id = str(interaction.user.id)
            success, stats = await self.get_bot_stats(user_id, bot_name)

            if success and stats:
                # Create an embed with the stats
                embed = discord.Embed(
                    title=f"Bot Status: {bot_name}",
                    color=(
                        discord.Color.green()
                        if stats["status"] == "running"
                        else discord.Color.red()
                    ),
                )

                embed.add_field(name="Status", value=stats["status"], inline=True)
                embed.add_field(name="Uptime", value=stats["uptime"], inline=True)
                embed.add_field(
                    name="Container ID", value=stats["container_id"], inline=True
                )
                embed.add_field(
                    name="CPU Usage", value=stats["cpu_percent"], inline=True
                )
                embed.add_field(
                    name="Memory Usage", value=stats["memory_usage"], inline=True
                )
                embed.add_field(
                    name="Memory %", value=stats["memory_percent"], inline=True
                )

                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"❌ Could not retrieve stats for bot {bot_name}"
                )

        # Setup admin commands
        @admin_commands.command(name="list-all", description="List all OpenShapes bots")
        async def list_all_bots_command(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            # Check admin permissions
            if not self.is_admin(interaction):
                await interaction.followup.send(
                    "❌ You don't have permission to use admin commands", ephemeral=True
                )
                return

            # Refresh the bot list first
            await self.refresh_bot_list()
            # Count total bots
            total_bots = sum(len(bots) for bots in self.active_bots.values())

            if total_bots == 0:
                await interaction.followup.send("No OpenShapes bots found")
                return

            # Create an embed to list all bots
            embed = discord.Embed(
                title="All OpenShapes Bots",
                description=f"Total: {total_bots} bot(s) across {len(self.active_bots)} user(s)",
                color=discord.Color.blue(),
            )

            for user_id, bots in self.active_bots.items():
                # Try to get user info
                try:
                    user = await self.fetch_user(int(user_id))
                    user_name = f"{user.name} ({user_id})"
                except:
                    user_name = f"User ID: {user_id}"

                # List bots for this user
                bot_list = []
                for bot_name, bot_info in bots.items():
                    status_emoji = "🟢" if bot_info["status"] == "running" else "🔴"
                    bot_list.append(f"{status_emoji} {bot_name}")

                embed.add_field(
                    name=user_name,
                    value="\n".join(bot_list) if bot_list else "No active bots",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        # FIX: Ensure this matches the signature expected by Discord
        @admin_commands.command(
            name="stats", description="Get system resource usage stats"
        )
        async def admin_stats_command(interaction: discord.Interaction):
            """Get system resource usage stats (admin only)"""
            await interaction.response.defer(thinking=True)

            # Check admin permissions
            if not self.is_admin(interaction):
                await interaction.followup.send(
                    "❌ You don't have permission to use admin commands", ephemeral=True
                )
                return

            try:
                # Get Docker system info
                info = self.docker_client.info()

                # Get container statistics
                containers = self.docker_client.containers.list()
                container_count = len(containers)
                running_count = sum(1 for c in containers if c.status == "running")

                # Get system memory info
                import psutil

                memory = psutil.virtual_memory()
                disk = psutil.disk_usage("/")

                # Create an embed with the stats
                embed = discord.Embed(
                    title="System Statistics", color=discord.Color.blue()
                )

                # Docker info
                embed.add_field(
                    name="Docker",
                    value=f"Version: {info.get('ServerVersion', 'Unknown')}\n"
                    f"Containers: {container_count} (Running: {running_count})\n"
                    f"Images: {len(self.docker_client.images.list())}",
                    inline=False,
                )

                # Host info
                embed.add_field(
                    name="Host",
                    value=f"OS: {info.get('OperatingSystem', 'Unknown')}\n"
                    f"Architecture: {info.get('Architecture', 'Unknown')}\n"
                    f"CPUs: {info.get('NCPU', 'Unknown')}",
                    inline=False,
                )

                # System resources
                embed.add_field(
                    name="CPU Usage", value=f"{psutil.cpu_percent()}%", inline=True
                )

                embed.add_field(
                    name="Memory Usage",
                    value=f"{memory.percent}% ({memory.used // (1024**3)}/{memory.total // (1024**3)} GB)",
                    inline=True,
                )

                embed.add_field(
                    name="Disk Usage",
                    value=f"{disk.percent}% ({disk.used // (1024**3)}/{disk.total // (1024**3)} GB)",
                    inline=True,
                )

                # OpenShapes stats
                embed.add_field(
                    name="OpenShapes",
                    value=f"Total bots: {sum(len(bots) for bots in self.active_bots.values())}\n"
                    f"Users: {len(self.active_bots)}\n"
                    f"Data directory: {self.config['data_dir']}",
                    inline=False,
                )

                await interaction.followup.send(embed=embed)

            except Exception as e:
                logger.error(f"Error getting system stats: {e}")
                await interaction.followup.send(
                    f"❌ Error getting system stats: {str(e)}"
                )

        @admin_commands.command(
            name="logs", description="Get logs from any bot (admin only)"
        )
        async def admin_logs_command(
            interaction: discord.Interaction,
            user_id: str,
            bot_name: str,
            lines: int = 50,
        ):
            await interaction.response.defer(thinking=True)
            # Check admin permissions
            if not self.is_admin(interaction):
                await interaction.followup.send(
                    "❌ You don't have permission to use admin commands", ephemeral=True
                )
                return

            success, logs = await self.get_bot_logs(user_id, bot_name, lines)

            if success:
                # Create a file with the logs if they're too long
                if len(logs) > 1950:
                    # Create a temporary file
                    with tempfile.NamedTemporaryFile(
                        suffix=".log", delete=False
                    ) as temp:
                        temp.write(logs.encode("utf-8"))
                        temp_name = temp.name

                    # Send the file
                    await interaction.followup.send(
                        f"Logs for {bot_name} (User: {user_id}):",
                        file=discord.File(temp_name, filename=f"{bot_name}_logs.log"),
                    )

                    # Delete the temporary file
                    os.unlink(temp_name)
                else:
                    await interaction.followup.send(
                        f"Logs for {bot_name} (User: {user_id}):\n```\n{logs}\n```"
                    )
            else:
                await interaction.followup.send(f"❌ {logs}")

        @admin_commands.command(
            name="kill", description="Force stop a bot (admin only)"
        )
        async def admin_kill_command(
            interaction: discord.Interaction, user_id: str, bot_name: str
        ):
            await interaction.response.defer(thinking=True)
            # Check admin permissions
            if not self.is_admin(interaction):
                await interaction.followup.send(
                    "❌ You don't have permission to use admin commands", ephemeral=True
                )
                return

            try:
                # Find the bot
                all_bots = self.active_bots.get(user_id, {})
                if bot_name not in all_bots:
                    await interaction.followup.send(
                        f"❌ Bot {bot_name} not found for user {user_id}"
                    )
                    return

                container_id = all_bots[bot_name]["container_id"]

                # Get the container
                container = self.docker_client.containers.get(container_id)

                # Kill the container
                container.kill()

                # Update active bots list
                await self.refresh_bot_list()

                await interaction.followup.send(f"✅ Bot {bot_name} forcefully stopped")

            except Exception as e:
                logger.error(f"Error killing bot: {e}")
                await interaction.followup.send(f"❌ Error killing bot: {str(e)}")

        @admin_commands.command(
            name="delete", description="Delete any bot (admin only)"
        )
        async def admin_delete_command(
            interaction: discord.Interaction, user_id: str, bot_name: str
        ):
            await interaction.response.defer(thinking=True)
            # Check admin permissions
            if not self.is_admin(interaction):
                await interaction.followup.send(
                    "❌ You don't have permission to use admin commands", ephemeral=True
                )
                return

            success, message = await self.delete_bot(user_id, bot_name)

            if success:
                await interaction.followup.send(f"✅ {message}")
            else:
                await interaction.followup.send(f"❌ {message}")

        @admin_commands.command(
            name="update", description="Update OpenShapes base image (admin only)"
        )
        async def admin_update_command(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            # Check admin permissions
            if not self.is_admin(interaction):
                await interaction.followup.send(
                    "❌ You don't have permission to use admin commands", ephemeral=True
                )
                return

            try:
                # Pull the latest image
                image = self.docker_client.images.pull(self.config["docker_base_image"])

                # Log the update
                logger.info(f"Updated base image: {image.id}")

                await interaction.followup.send(f"✅ Base image updated to: {image.id}")

            except Exception as e:
                logger.error(f"Error updating base image: {e}")
                await interaction.followup.send(
                    f"❌ Error updating base image: {str(e)}"
                )

        @admin_commands.command(
            name="add-admin", description="Add a user to admin list (admin only)"
        )
        async def admin_add_admin_command(
            interaction: discord.Interaction, user_id: str
        ):
            await interaction.response.defer(thinking=True)
            # Check admin permissions
            if not self.is_admin(interaction):
                await interaction.followup.send(
                    "❌ You don't have permission to use admin commands", ephemeral=True
                )
                return

            try:
                # Validate user ID
                try:
                    user = await self.fetch_user(int(user_id))
                except:
                    await interaction.followup.send(f"❌ Invalid user ID: {user_id}")
                    return

                # Add to admin users if not already there
                if user_id not in self.config["admin_users"]:
                    self.config["admin_users"].append(user_id)
                    self.save_config()

                    await interaction.followup.send(
                        f"✅ Added {user.name} ({user_id}) to admin list"
                    )
                else:
                    await interaction.followup.send(
                        f"User {user.name} ({user_id}) is already an admin"
                    )

            except Exception as e:
                logger.error(f"Error adding admin: {e}")
                await interaction.followup.send(f"❌ Error adding admin: {str(e)}")

        @admin_commands.command(
            name="remove-admin",
            description="Remove a user from admin list (admin only)",
        )
        async def admin_remove_admin_command(
            interaction: discord.Interaction, user_id: str
        ):
            await interaction.response.defer(thinking=True)
            # Check admin permissions
            if not self.is_admin(interaction):
                await interaction.followup.send(
                    "❌ You don't have permission to use admin commands", ephemeral=True
                )
                return

            try:
                # Remove from admin users
                if user_id in self.config["admin_users"]:
                    self.config["admin_users"].remove(user_id)
                    self.save_config()

                    await interaction.followup.send(
                        f"✅ Removed user {user_id} from admin list"
                    )
                else:
                    await interaction.followup.send(
                        f"User {user_id} is not in the admin list"
                    )

            except Exception as e:
                logger.error(f"Error removing admin: {e}")
                await interaction.followup.send(f"❌ Error removing admin: {str(e)}")

        @admin_commands.command(
            name="set-limit", description="Set max bots per user (admin only)"
        )
        async def admin_set_limit_command(interaction: discord.Interaction, limit: int):
            await interaction.response.defer(thinking=True)
            # Check admin permissions
            if not self.is_admin(interaction):
                await interaction.followup.send(
                    "❌ You don't have permission to use admin commands", ephemeral=True
                )
                return

            try:
                # Validate limit
                if limit < 1:
                    await interaction.followup.send("❌ Limit must be at least 1")
                    return

                # Update limit
                old_limit = self.config["max_bots_per_user"]
                self.config["max_bots_per_user"] = limit
                self.save_config()

                await interaction.followup.send(
                    f"✅ Updated max bots per user from {old_limit} to {limit}"
                )

            except Exception as e:
                logger.error(f"Error setting limit: {e}")
                await interaction.followup.send(f"❌ Error setting limit: {str(e)}")

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        logger.info(f"Discord.py version: {discord.__version__}")
        logger.info("Bot is ready")

    async def _create_monitor_task(self):
        """Create the container monitoring task"""

        @tasks.loop(minutes=5)
        async def monitor_containers_task():
            """Periodically check container status and refresh the active bots list"""
            await self.refresh_bot_list()
            logger.info("Container monitor: Refreshed bot list")

        return monitor_containers_task
        self.monitor_containers.start()

        # Load active bots from Docker
        await self.refresh_bot_list()

    async def refresh_bot_list(self) -> None:
        """Refresh the list of active bots from Docker containers"""
        try:
            containers = self.docker_client.containers.list(all=True)

            # Reset active bots dict
            self.active_bots = {}

            for container in containers:
                # Only consider containers with our label
                if container.labels.get("managed_by") == "openshapes_manager":
                    user_id = container.labels.get("user_id")
                    bot_name = container.labels.get("bot_name")

                    if user_id and bot_name:
                        # Add to active bots
                        if user_id not in self.active_bots:
                            self.active_bots[user_id] = {}

                        self.active_bots[user_id][bot_name] = {
                            "container_id": container.id,
                            "status": container.status,
                            "created": container.attrs.get("Created"),
                            "name": container.name,
                        }

            logger.info(
                f"Refreshed bot list: {len(self.active_bots)} users with active bots"
            )
        except Exception as e:
            logger.error(f"Error refreshing bot list: {e}")

    def is_admin(self, interaction: discord.Interaction) -> bool:
        """Check if a user has admin permissions"""
        user_id = str(interaction.user.id)

        # Check if user is in admin users list
        if user_id in self.config["admin_users"]:
            return True

        # Check if user has an admin role
        if interaction.guild:
            user_roles = [str(role.id) for role in interaction.user.roles]
            for role_id in self.config["admin_roles"]:
                if role_id in user_roles:
                    return True

        return False

    def get_user_bots(self, user_id: str) -> Dict[str, dict]:
        """Get all bots for a specific user"""
        return self.active_bots.get(user_id, {})

    def get_user_bot_count(self, user_id: str) -> int:
        """Get the number of bots a user has"""
        return len(self.get_user_bots(user_id))

    def get_user_data_dir(self, user_id: str) -> str:
        """Get the data directory for a specific user"""
        user_dir = os.path.join(self.config["data_dir"], "users", user_id)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def get_bot_config_dir(self, user_id: str, bot_name: str) -> str:
        """Get the configuration directory for a specific bot"""
        config_dir = os.path.join(self.get_user_data_dir(user_id), bot_name)
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def get_bot_log_file(self, user_id: str, bot_name: str) -> str:
        """Get the log file path for a specific bot"""
        log_dir = os.path.join(self.config["data_dir"], "logs")
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, f"{user_id}_{bot_name}.log")

    async def create_bot(
        self,
        user_id: str,
        bot_name: str,
        config_json: str,
        bot_token: str,
        brain_json: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Create a new OpenShapes bot for a user

        Args:
            user_id: Discord user ID
            bot_name: Name for the bot
            config_json: Contents of config.json
            bot_token: Discord bot token
            brain_json: Contents of brain.json (optional)

        Returns:
            (success, message)
        """
        try:
            # Validate bot name (alphanumeric with underscores only)
            if not bot_name.replace("_", "").isalnum():
                return (
                    False,
                    "Bot name must contain only letters, numbers, and underscores",
                )

            # Check if user already has a bot with this name
            user_bots = self.get_user_bots(user_id)
            if bot_name in user_bots:
                return False, f"You already have a bot named {bot_name}"

            # Check if user has reached max bots limit (unless admin)
            is_admin = str(user_id) in self.config["admin_users"]
            if (
                not is_admin
                and self.get_user_bot_count(user_id) >= self.config["max_bots_per_user"]
            ):
                return (
                    False,
                    f"You have reached the maximum limit of {self.config['max_bots_per_user']} bots",
                )

            # Parse and validate config_json
            try:
                config_data = json.loads(config_json)
            except json.JSONDecodeError:
                return False, "Invalid JSON in config.json"

            # Parse and validate brain_json if provided
            brain_data = None
            if brain_json:
                try:
                    brain_data = json.loads(brain_json)
                except json.JSONDecodeError:
                    return False, "Invalid JSON in brain.json"

            # Get directory for this bot
            bot_dir = self.get_bot_config_dir(user_id, bot_name)

            # Save config.json
            with open(os.path.join(bot_dir, "config.json"), "w") as f:
                json.dump(config_data, f, indent=2)

            # Save brain.json if provided
            if brain_data:
                with open(os.path.join(bot_dir, "brain.json"), "w") as f:
                    json.dump(brain_data, f, indent=2)

            # Run the OpenShapes parser to generate character_config.json
            parser_result = await self._run_parser(bot_dir)
            if not parser_result[0]:
                return parser_result  # Return the error

            # Update character_config.json with the provided token
            try:
                config_path = os.path.join(bot_dir, "character_config.json")
                with open(config_path, "r") as f:
                    char_config = json.load(f)

                # Set the bot token in the configuration
                char_config["bot_token"] = bot_token

                # Save updated config
                with open(config_path, "w") as f:
                    json.dump(char_config, f, indent=2)
            except Exception as e:
                logger.error(f"Error updating character_config.json with token: {e}")
                return False, f"Error updating configuration: {str(e)}"

            # Start the container with the new configuration
            container_result = await self._start_bot_container(
                user_id, bot_name, bot_dir
            )
            if not container_result[0]:
                return container_result  # Return the error

            # Update active bots list
            await self.refresh_bot_list()

            return True, f"Bot {bot_name} created and started successfully"

        except Exception as e:
            logger.error(f"Error creating bot: {e}")
            return False, f"Error creating bot: {str(e)}"

    async def _run_parser(self, bot_dir: str) -> Tuple[bool, str]:
        """Run the OpenShapes parser in the bot directory"""
        try:
            # Check if config.json exists
            config_path = os.path.join(bot_dir, "config.json")
            if not os.path.exists(config_path):
                return False, "config.json not found"

            # Copy the parser.py file to the bot directory
            # Assumes parser.py is in the same directory as your bot code
            parser_source = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "parser.py"
            )

            # If the file doesn't exist at that location, try looking in the current directory
            if not os.path.exists(parser_source):
                current_dir = os.getcwd()
                parser_source = os.path.join(current_dir, "parser.py")

            parser_dest = os.path.join(bot_dir, "parser.py")

            try:
                import shutil

                shutil.copyfile(parser_source, parser_dest)
                logger.info(f"Copied parser.py from {parser_source} to {parser_dest}")
            except Exception as e:
                logger.error(f"Failed to copy parser.py: {e}")
                return False, f"Failed to copy parser.py: {str(e)}"

            # Create a simpler run script that doesn't require input
            parser_script = """
import os
import sys
import traceback

try:
    # Print current working directory and available files
    print(f"Working directory: {os.getcwd()}")
    print(f"Files in current directory: {os.listdir('.')}")
    
    # Import our local parser.py
    import parser
    
    # Run the parser
    parser.main()
    
except Exception as e:
    print(f"ERROR IN PARSER: {str(e)}")
    traceback.print_exc()
    sys.exit(1)
    """

            parser_script_path = os.path.join(bot_dir, "run_parser.py")
            with open(parser_script_path, "w") as f:
                f.write(parser_script)

            logger.info(f"Running parser in directory: {os.path.abspath(bot_dir)}")

            # Create a temporary Docker container to run the parser
            container = self.docker_client.containers.run(
                image=self.config["docker_base_image"],
                command="python run_parser.py",
                volumes={
                    os.path.abspath(bot_dir): {"bind": "/app/selfhost", "mode": "rw"}
                },
                working_dir="/app/selfhost",
                remove=False,  # Keep container for debugging
                detach=True,
                environment={
                    "PYTHONPATH": "/app/selfhost"
                },  # Setting the PYTHONPATH to include the current directory
            )

            logger.info(f"Created parser container with ID: {container.id}")

            # Wait for the container to complete with timeout
            try:
                result = container.wait(timeout=30)
                logger.info(f"Container exit result: {result}")

                # Get logs regardless of exit code
                logs = container.logs().decode("utf-8")
                logger.info(f"Container logs: {logs}")

                # Now remove the container
                try:
                    container.remove()
                except Exception as e:
                    logger.warning(f"Failed to remove container: {e}")

            except Exception as e:
                logger.error(f"Error waiting for container: {e}")
                try:
                    # Try to get logs even if wait failed
                    logs = container.logs().decode("utf-8")
                    logger.info(f"Container logs after wait error: {logs}")

                    # Try to stop and remove the container
                    container.stop(timeout=5)
                    container.remove()
                except Exception as cleanup_error:
                    logger.warning(f"Error during container cleanup: {cleanup_error}")
                return False, f"Error waiting for parser container: {str(e)}"

            # Remove the temporary script
            try:
                os.remove(parser_script_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary script: {e}")

            if result["StatusCode"] != 0:
                return (
                    False,
                    f"Parser failed with exit code {result['StatusCode']}:\n{logs}",
                )

            # Check if character_config.json was created
            if not os.path.exists(os.path.join(bot_dir, "character_config.json")):
                return (
                    False,
                    f"Parser did not generate character_config.json. Logs:\n{logs}",
                )

            return True, "Parser ran successfully"

        except Exception as e:
            logger.error(f"Error running parser: {e}")
            return False, f"Error running parser: {str(e)}"

    async def _start_bot_container(
        self, user_id: str, bot_name: str, bot_dir: str
    ) -> Tuple[bool, str]:
        """Start a Docker container for the bot"""
        try:
            # Container name will be openshape_{user_id}_{bot_name}
            container_name = f"openshape_{user_id}_{bot_name}"

            # Check if container already exists
            try:
                existing = self.docker_client.containers.get(container_name)
                # If it exists but is stopped, remove it
                if existing.status != "running":
                    existing.remove()
                else:
                    return False, f"Container {container_name} is already running"
            except docker.errors.NotFound:
                # Container doesn't exist, which is fine
                pass

            # Map the bot directory to a config directory in the container
            volumes = {os.path.abspath(bot_dir): {"bind": "/app/config", "mode": "rw"}}

            # Create data directories if they don't exist
            character_data_dir = os.path.join(bot_dir, "character_data")
            os.makedirs(character_data_dir, exist_ok=True)

            # Environment variables
            environment = {
                "OPENSHAPE_BOT_NAME": bot_name,
                "OPENSHAPE_USER_ID": user_id,
                "OPENSHAPE_CONFIG_DIR": "/app/config",  # Tell the bot where to find configs
            }

            # Create a startup script to copy configs and start the bot
            startup_script = """#!/bin/bash
# Copy config files to the selfhost directory
cp -v /app/config/character_config.json /app/selfhost/
cp -v /app/config/config.json /app/selfhost/
if [ -f /app/config/brain.json ]; then
    cp -v /app/config/brain.json /app/selfhost/
fi

# Create character_data directory if it doesn't exist
mkdir -p /app/selfhost/character_data

# Copy character_data if it exists
if [ -d /app/config/character_data ]; then
    cp -rv /app/config/character_data/* /app/selfhost/character_data/
fi

# Start the bot
cd /app/selfhost
python bot.py
"""
            # Write the script to the bot directory
            script_path = os.path.join(bot_dir, "start_bot.sh")
            with open(script_path, "w") as f:
                f.write(startup_script)

            # Make the script executable
            os.chmod(script_path, 0o755)

            # Start the container
            container = self.docker_client.containers.run(
                image=self.config["docker_base_image"],
                name=container_name,
                volumes=volumes,
                environment=environment,
                command=["/bin/bash", "/app/config/start_bot.sh"],
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                labels={
                    "managed_by": "openshapes_manager",
                    "user_id": user_id,
                    "bot_name": bot_name,
                },
            )

            logger.info(f"Started container {container_name} with ID {container.id}")

            return True, f"Container {container_name} started"

        except Exception as e:
            logger.error(f"Error starting container: {e}")
            return False, f"Error starting container: {str(e)}"

    async def start_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        """Start a stopped bot"""
        try:
            # Verify ownership
            user_bots = self.get_user_bots(user_id)
            if bot_name not in user_bots:
                return False, f"Bot {bot_name} not found"

            container_id = user_bots[bot_name]["container_id"]

            # Get the container
            container = self.docker_client.containers.get(container_id)

            # Check if already running
            if container.status == "running":
                return False, f"Bot {bot_name} is already running"

            # Start the container
            container.start()

            # Update active bots list
            await self.refresh_bot_list()

            return True, f"Bot {bot_name} started"

        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            return False, f"Error starting bot: {str(e)}"

    async def stop_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        """Stop a running bot"""
        try:
            # Verify ownership
            user_bots = self.get_user_bots(user_id)
            if bot_name not in user_bots:
                return False, f"Bot {bot_name} not found"

            container_id = user_bots[bot_name]["container_id"]

            # Get the container
            container = self.docker_client.containers.get(container_id)

            # Check if already stopped
            if container.status != "running":
                return False, f"Bot {bot_name} is not running"

            # Stop the container
            container.stop(timeout=10)  # Give 10 seconds for graceful shutdown

            # Update active bots list
            await self.refresh_bot_list()

            return True, f"Bot {bot_name} stopped"

        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
            return False, f"Error stopping bot: {str(e)}"

    async def restart_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        """Restart a bot"""
        try:
            # Verify ownership
            user_bots = self.get_user_bots(user_id)
            if bot_name not in user_bots:
                return False, f"Bot {bot_name} not found"

            container_id = user_bots[bot_name]["container_id"]

            # Get the container
            container = self.docker_client.containers.get(container_id)

            # Restart the container
            container.restart(
                timeout=10
            )  # Give 10 seconds for graceful shutdown before restart

            # Update active bots list
            await self.refresh_bot_list()

            return True, f"Bot {bot_name} restarted"

        except Exception as e:
            logger.error(f"Error restarting bot: {e}")
            return False, f"Error restarting bot: {str(e)}"

    async def delete_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        """Delete a bot completely"""
        try:
            # Skip ownership verification for admins
            is_admin = str(user_id) in self.config["admin_users"]

            if not is_admin:
                # Verify ownership
                user_bots = self.get_user_bots(user_id)
                if bot_name not in user_bots:
                    return False, f"Bot {bot_name} not found"

            # Get container ID (admins can specify a user_id different from their own)
            all_bots = self.active_bots.get(user_id, {})
            if bot_name not in all_bots:
                return False, f"Bot {bot_name} not found for user {user_id}"

            container_id = all_bots[bot_name]["container_id"]

            # Try to get and remove the container
            try:
                container = self.docker_client.containers.get(container_id)

                # Stop if running
                if container.status == "running":
                    container.stop(timeout=5)

                # Remove the container
                container.remove()
                logger.info(f"Removed container for bot {bot_name}")
            except Exception as e:
                logger.warning(f"Error removing container: {e}")
                # Continue with directory removal even if container removal fails

            # Get the bot directory
            bot_dir = self.get_bot_config_dir(user_id, bot_name)

            # Remove the bot directory
            import shutil

            try:
                shutil.rmtree(bot_dir)
                logger.info(f"Removed directory for bot {bot_name}: {bot_dir}")
            except Exception as e:
                logger.error(f"Error removing bot directory: {e}")
                return False, f"Error removing bot directory: {str(e)}"

            # Update active bots list
            await self.refresh_bot_list()

            return True, f"Bot {bot_name} deleted successfully"

        except Exception as e:
            logger.error(f"Error deleting bot: {e}")
            return False, f"Error deleting bot: {str(e)}"

    async def get_bot_logs(
        self, user_id: str, bot_name: str, lines: int = 20
    ) -> Tuple[bool, str]:
        """Get logs from a bot container"""
        try:
            # Skip ownership verification for admins
            is_admin = str(user_id) in self.config["admin_users"]

            if not is_admin:
                # Verify ownership
                user_bots = self.get_user_bots(user_id)
                if bot_name not in user_bots:
                    return False, f"Bot {bot_name} not found"

            # Get container ID (admins can specify a user_id different from their own)
            all_bots = self.active_bots.get(user_id, {})
            if bot_name not in all_bots:
                return False, f"Bot {bot_name} not found for user {user_id}"

            container_id = all_bots[bot_name]["container_id"]

            # Get the container
            container = self.docker_client.containers.get(container_id)

            # Get logs
            logs = container.logs(tail=lines).decode("utf-8")

            if not logs:
                logs = "No logs available"

            return True, logs

        except Exception as e:
            logger.error(f"Error getting bot logs: {e}")
            return False, f"Error getting bot logs: {str(e)}"

    async def get_bot_stats(self, user_id: str, bot_name: str) -> Tuple[bool, dict]:
        """Get detailed stats for a bot"""
        try:
            # Verify ownership
            user_bots = self.get_user_bots(user_id)
            if bot_name not in user_bots:
                return False, None

            container_id = user_bots[bot_name]["container_id"]

            # Get the container
            container = self.docker_client.containers.get(container_id)

            # Get container stats
            stats = container.stats(stream=False)

            # Calculate CPU and memory usage
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )
            cpu_count = (
                len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])
                if "percpu_usage" in stats["cpu_stats"]["cpu_usage"]
                else 1
            )

            cpu_percent = 0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100

            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_limit = stats["memory_stats"].get("limit", 1)
            memory_percent = (
                (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
            )

            # Calculate uptime
            import datetime

            started_at = container.attrs.get("State", {}).get("StartedAt", "")
            if started_at:
                start_time = datetime.datetime.fromisoformat(
                    started_at.replace("Z", "+00:00")
                )
                uptime = datetime.datetime.now(datetime.timezone.utc) - start_time
                uptime_str = str(uptime).split(".")[0]  # Remove microseconds
            else:
                uptime_str = "Unknown"

            # Format memory usage
            if memory_usage < 1024 * 1024:
                memory_usage_str = f"{memory_usage / 1024:.2f} KB"
            else:
                memory_usage_str = f"{memory_usage / (1024 * 1024):.2f} MB"

            return True, {
                "status": container.status,
                "uptime": uptime_str,
                "container_id": container_id[:12],  # Short ID
                "cpu_percent": f"{cpu_percent:.2f}%",
                "memory_usage": memory_usage_str,
                "memory_percent": f"{memory_percent:.2f}%",
            }

        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            return False, None


# Main entry point
def main():
    """Main entry point for the bot"""
    bot = OpenShapesManager()
    token = bot.config.get("token")

    if token == "YOUR_DISCORD_BOT_TOKEN":
        print("Please set your bot token in manager_config.json")
        return

    bot.run(token)


if __name__ == "__main__":
    main()
