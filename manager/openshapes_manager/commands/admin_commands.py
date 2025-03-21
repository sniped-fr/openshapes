import discord
import tempfile
import os
import psutil
from typing import Dict, Any
from abc import ABC, abstractmethod


class AdminCommandResult:
    def __init__(self, success: bool, message: str, data: Any = None):
        self.success = success
        self.message = message
        self.data = data


class AdminCommand(ABC):
    def __init__(self, bot):
        self.bot = bot
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        await interaction.response.defer(thinking=True)
        
        if not self.bot.is_admin(interaction):
            await interaction.followup.send(
                "❌ You don't have permission to use admin commands", ephemeral=True
            )
            return
        
        result = await self._execute_command(interaction, **kwargs)
        
        if result.success:
            if isinstance(result.data, discord.Embed):
                await interaction.followup.send(embed=result.data)
            elif isinstance(result.data, discord.File):
                await interaction.followup.send(result.message, file=result.data)
            else:
                await interaction.followup.send(f"✅ {result.message}")
        else:
            await interaction.followup.send(f"❌ {result.message}")
    
    @abstractmethod
    async def _execute_command(self, interaction: discord.Interaction, **kwargs) -> AdminCommandResult:
        pass


class ListAllBotsCommand(AdminCommand):
    async def _execute_command(self, interaction: discord.Interaction, **kwargs) -> AdminCommandResult:
        try:
            await self.bot.refresh_bot_list()
            total_bots = sum(len(bots) for bots in self.bot.container_manager.registry.active_bots.values())
            
            if total_bots == 0:
                return AdminCommandResult(True, "No OpenShapes bots found")
            
            embed = await self._create_bots_embed(total_bots)
            return AdminCommandResult(True, "Bot list retrieved", embed)
        
        except Exception as e:
            self.bot.logger.error(f"Error listing all bots: {e}")
            return AdminCommandResult(False, f"Error listing all bots: {str(e)}")
    
    async def _create_bots_embed(self, total_bots: int) -> discord.Embed:
        active_bots = self.bot.container_manager.registry.active_bots
        
        embed = discord.Embed(
            title="All OpenShapes Bots",
            description=f"Total: {total_bots} bot(s) across {len(active_bots)} user(s)",
            color=discord.Color.blue(),
        )
        
        for user_id, bots in active_bots.items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                user_name = f"{user.name} ({user_id})"
            except Exception:
                user_name = f"User ID: {user_id}"
            
            bot_list = []
            for bot_name, bot_info in bots.items():
                status_emoji = "🟢" if bot_info["status"] == "running" else "🔴"
                bot_list.append(f"{status_emoji} {bot_name}")
            
            embed.add_field(
                name=user_name,
                value="\n".join(bot_list) if bot_list else "No active bots",
                inline=False,
            )
        
        return embed


class SystemStatsCommand(AdminCommand):
    async def _execute_command(self, interaction: discord.Interaction, **kwargs) -> AdminCommandResult:
        try:
            info = self.bot.container_manager.docker_client.info()
            embed = await self._create_stats_embed(info)
            return AdminCommandResult(True, "System stats retrieved", embed)
        
        except Exception as e:
            self.bot.logger.error(f"Error getting system stats: {e}")
            return AdminCommandResult(False, f"Error getting system stats: {str(e)}")
    
    async def _create_stats_embed(self, info: Dict[str, Any]) -> discord.Embed:
        docker_client = self.bot.container_manager.docker_client
        
        containers = docker_client.containers.list()
        container_count = len(containers)
        running_count = sum(1 for c in containers if c.status == "running")
        
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        embed = discord.Embed(
            title="System Statistics", color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Docker",
            value=f"Version: {info.get('ServerVersion', 'Unknown')}\n"
                  f"Containers: {container_count} (Running: {running_count})\n"
                  f"Images: {len(docker_client.images.list())}",
            inline=False,
        )
        
        embed.add_field(
            name="Host",
            value=f"OS: {info.get('OperatingSystem', 'Unknown')}\n"
                  f"Architecture: {info.get('Architecture', 'Unknown')}\n"
                  f"CPUs: {info.get('NCPU', 'Unknown')}",
            inline=False,
        )
        
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
        
        active_bots = self.bot.container_manager.registry.active_bots
        embed.add_field(
            name="OpenShapes",
            value=f"Total bots: {sum(len(bots) for bots in active_bots.values())}\n"
                  f"Users: {len(active_bots)}\n"
                  f"Data directory: {self.bot.config_manager.get('data_dir', 'data')}",
            inline=False,
        )
        
        return embed


class BotLogsCommand(AdminCommand):
    async def _execute_command(
        self, interaction: discord.Interaction, user_id: str, bot_name: str, lines: int = 50, **kwargs
    ) -> AdminCommandResult:
        try:
            success, logs = await self.bot.get_bot_logs(user_id, bot_name, lines)
            
            if not success:
                return AdminCommandResult(False, logs)
            
            if len(logs) > 1950:
                return await self._create_log_file(logs, bot_name, user_id)
            else:
                return AdminCommandResult(
                    True, f"Logs for {bot_name} (User: {user_id}):\n```\n{logs}\n```"
                )
        
        except Exception as e:
            self.bot.logger.error(f"Error getting bot logs: {e}")
            return AdminCommandResult(False, f"Error getting bot logs: {str(e)}")
    
    async def _create_log_file(self, logs: str, bot_name: str, user_id: str) -> AdminCommandResult:
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as temp:
            temp.write(logs.encode("utf-8"))
            temp_name = temp.name
        
        log_file = discord.File(temp_name, filename=f"{bot_name}_logs.log")
        message = f"Logs for {bot_name} (User: {user_id}):"
        
        # Delete the temp file after we've created the discord.File object
        os.unlink(temp_name)
        
        return AdminCommandResult(True, message, log_file)


class KillBotCommand(AdminCommand):
    async def _execute_command(
        self, interaction: discord.Interaction, user_id: str, bot_name: str, **kwargs
    ) -> AdminCommandResult:
        try:
            active_bots = self.bot.container_manager.registry.active_bots
            all_bots = active_bots.get(user_id, {})
            
            if bot_name not in all_bots:
                return AdminCommandResult(False, f"Bot {bot_name} not found for user {user_id}")
            
            container_id = all_bots[bot_name]["container_id"]
            container = self.bot.container_manager.docker_client.containers.get(container_id)
            container.kill()
            
            await self.bot.refresh_bot_list()
            return AdminCommandResult(True, f"Bot {bot_name} forcefully stopped")
        
        except Exception as e:
            self.bot.logger.error(f"Error killing bot: {e}")
            return AdminCommandResult(False, f"Error killing bot: {str(e)}")


class DeleteBotCommand(AdminCommand):
    async def _execute_command(
        self, interaction: discord.Interaction, user_id: str, bot_name: str, **kwargs
    ) -> AdminCommandResult:
        try:
            success, message = await self.bot.delete_bot(user_id, bot_name)
            return AdminCommandResult(success, message)
        
        except Exception as e:
            self.bot.logger.error(f"Error deleting bot: {e}")
            return AdminCommandResult(False, f"Error deleting bot: {str(e)}")


class UpdateImageCommand(AdminCommand):
    async def _execute_command(self, interaction: discord.Interaction, **kwargs) -> AdminCommandResult:
        try:
            docker_base_image = self.bot.config_manager.get("docker_base_image")
            image = self.bot.container_manager.docker_client.images.pull(docker_base_image)
            self.bot.logger.info(f"Updated base image: {image.id}")
            return AdminCommandResult(True, f"Base image updated to: {image.id}")
        
        except Exception as e:
            self.bot.logger.error(f"Error updating base image: {e}")
            return AdminCommandResult(False, f"Error updating base image: {str(e)}")


class AdminUserManagementCommand(AdminCommand):
    async def _execute_command(
        self, interaction: discord.Interaction, user_id: str, action: str, **kwargs
    ) -> AdminCommandResult:
        try:
            if action == "add":
                return await self._add_admin(user_id)
            elif action == "remove":
                return await self._remove_admin(user_id)
            else:
                return AdminCommandResult(False, f"Unknown action: {action}")
        
        except Exception as e:
            self.bot.logger.error(f"Error managing admin users: {e}")
            return AdminCommandResult(False, f"Error managing admin users: {str(e)}")
    
    async def _add_admin(self, user_id: str) -> AdminCommandResult:
        try:
            user = await self.bot.fetch_user(int(user_id))
        except Exception:
            return AdminCommandResult(False, f"Invalid user ID: {user_id}")
        
        admin_users = self.bot.config_manager.get("admin_users", [])
        
        if user_id not in admin_users:
            admin_users.append(user_id)
            self.bot.config_manager.set("admin_users", admin_users)
            self.bot.save_config()
            return AdminCommandResult(True, f"Added {user.name} ({user_id}) to admin list")
        else:
            return AdminCommandResult(True, f"User {user.name} ({user_id}) is already an admin")
    
    async def _remove_admin(self, user_id: str) -> AdminCommandResult:
        admin_users = self.bot.config_manager.get("admin_users", [])
        
        if user_id in admin_users:
            admin_users.remove(user_id)
            self.bot.config_manager.set("admin_users", admin_users)
            self.bot.save_config()
            return AdminCommandResult(True, f"Removed user {user_id} from admin list")
        else:
            return AdminCommandResult(False, f"User {user_id} is not in the admin list")


class SetBotLimitCommand(AdminCommand):
    async def _execute_command(
        self, interaction: discord.Interaction, limit: int, **kwargs
    ) -> AdminCommandResult:
        try:
            if limit < 1:
                return AdminCommandResult(False, "Limit must be at least 1")
            
            old_limit = self.bot.config_manager.get("max_bots_per_user", 5)
            self.bot.config_manager.set("max_bots_per_user", limit)
            self.bot.save_config()
            
            return AdminCommandResult(True, f"Updated max bots per user from {old_limit} to {limit}")
        
        except Exception as e:
            self.bot.logger.error(f"Error setting limit: {e}")
            return AdminCommandResult(False, f"Error setting limit: {str(e)}")


class AdminCommandRegistry:
    def __init__(self, bot):
        self.bot = bot
        self.commands = {
            "list-all": ListAllBotsCommand(bot),
            "stats": SystemStatsCommand(bot),
            "logs": BotLogsCommand(bot),
            "kill": KillBotCommand(bot),
            "delete": DeleteBotCommand(bot),
            "update": UpdateImageCommand(bot),
            "add-admin": lambda: AdminUserManagementCommand(bot),
            "remove-admin": lambda: AdminUserManagementCommand(bot),
            "set-limit": SetBotLimitCommand(bot)
        }


def setup_admin_commands(bot, admin_commands):
    registry = AdminCommandRegistry(bot)
    
    @admin_commands.command(name="list-all", description="List all OpenShapes bots")
    async def list_all_bots_command(interaction: discord.Interaction):
        await registry.commands["list-all"].execute(interaction)
    
    @admin_commands.command(name="stats", description="Get system resource usage stats")
    async def admin_stats_command(interaction: discord.Interaction):
        await registry.commands["stats"].execute(interaction)
    
    @admin_commands.command(name="logs", description="Get logs from any bot (admin only)")
    async def admin_logs_command(
        interaction: discord.Interaction,
        user_id: str,
        bot_name: str,
        lines: int = 50,
    ):
        await registry.commands["logs"].execute(
            interaction, user_id=user_id, bot_name=bot_name, lines=lines
        )
    
    @admin_commands.command(name="kill", description="Force stop a bot (admin only)")
    async def admin_kill_command(interaction: discord.Interaction, user_id: str, bot_name: str):
        await registry.commands["kill"].execute(interaction, user_id=user_id, bot_name=bot_name)
    
    @admin_commands.command(name="delete", description="Delete any bot (admin only)")
    async def admin_delete_command(interaction: discord.Interaction, user_id: str, bot_name: str):
        await registry.commands["delete"].execute(interaction, user_id=user_id, bot_name=bot_name)
    
    @admin_commands.command(name="update", description="Update OpenShapes base image (admin only)")
    async def admin_update_command(interaction: discord.Interaction):
        await registry.commands["update"].execute(interaction)
    
    @admin_commands.command(name="add-admin", description="Add a user to admin list (admin only)")
    async def admin_add_admin_command(interaction: discord.Interaction, user_id: str):
        command = registry.commands["add-admin"]()
        await command.execute(interaction, user_id=user_id, action="add")
    
    @admin_commands.command(name="remove-admin", description="Remove a user from admin list (admin only)")
    async def admin_remove_admin_command(interaction: discord.Interaction, user_id: str):
        command = registry.commands["remove-admin"]()
        await command.execute(interaction, user_id=user_id, action="remove")
    
    @admin_commands.command(name="set-limit", description="Set max bots per user (admin only)")
    async def admin_set_limit_command(interaction: discord.Interaction, limit: int):
        await registry.commands["set-limit"].execute(interaction, limit=limit)
