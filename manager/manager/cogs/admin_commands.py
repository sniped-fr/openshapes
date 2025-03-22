import discord
import tempfile
import os
import psutil
from discord import app_commands
from discord.ext import commands

class AdminCommands(commands.GroupCog, group_name="admin", group_description="Admin commands for bot management"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="list-all", description="List all OpenShapes bots")
    async def list_all(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        if not self.bot.is_admin(interaction):
            await interaction.followup.send("❌ You don't have permission to use admin commands", ephemeral=True)
            return

        await self.bot.refresh_bot_list()
        total_bots = sum(len(bots) for bots in self.bot.container_manager.active_bots.values())

        if total_bots == 0:
            await interaction.followup.send("No OpenShapes bots found")
            return

        embed = discord.Embed(
            title="All OpenShapes Bots",
            description=f"Total: {total_bots} bot(s) across {len(self.bot.container_manager.active_bots)} user(s)",
            color=discord.Color.blue(),
        )

        for user_id, bots in self.bot.container_manager.active_bots.items():
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

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stats", description="Get system resource usage stats")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        if not self.bot.is_admin(interaction):
            await interaction.followup.send("❌ You don't have permission to use admin commands", ephemeral=True)
            return

        try:
            info = self.bot.container_manager.docker_client.info()
            containers = self.bot.container_manager.docker_client.containers.list()
            container_count = len(containers)
            running_count = sum(1 for c in containers if c.status == "running")
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            embed = discord.Embed(title="System Statistics", color=discord.Color.blue())
            embed.add_field(
                name="Docker",
                value=f"Version: {info.get('ServerVersion', 'Unknown')}\n"
                      f"Containers: {container_count} (Running: {running_count})\n"
                      f"Images: {len(self.bot.container_manager.docker_client.images.list())}",
                inline=False,
            )
            embed.add_field(
                name="Host",
                value=f"OS: {info.get('OperatingSystem', 'Unknown')}\n"
                      f"Architecture: {info.get('Architecture', 'Unknown')}\n"
                      f"CPUs: {info.get('NCPU', 'Unknown')}",
                inline=False,
            )
            embed.add_field(name="CPU Usage", value=f"{psutil.cpu_percent()}%", inline=True)
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
            embed.add_field(
                name="OpenShapes",
                value=f"Total bots: {sum(len(bots) for bots in self.bot.container_manager.active_bots.values())}\n"
                      f"Users: {len(self.bot.container_manager.active_bots)}\n"
                      f"Data directory: {self.bot.config['data_dir']}",
                inline=False,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            self.bot.logger.error(f"Error getting system stats: {e}")
            await interaction.followup.send(f"❌ Error getting system stats: {str(e)}")

    @app_commands.command(name="logs", description="Get logs from any bot (admin only)")
    async def logs(self, interaction: discord.Interaction, user_id: str, bot_name: str, lines: int = 50):
        await interaction.response.defer(thinking=True)
        if not self.bot.is_admin(interaction):
            await interaction.followup.send("❌ You don't have permission to use admin commands", ephemeral=True)
            return

        success, logs = await self.bot.get_bot_logs(user_id, bot_name, lines)
        if success:
            if len(logs) > 1950:
                with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as temp:
                    temp.write(logs.encode("utf-8"))
                    temp_name = temp.name
                await interaction.followup.send(
                    f"Logs for {bot_name} (User: {user_id}):",
                    file=discord.File(temp_name, filename=f"{bot_name}_logs.log"),
                )
                os.unlink(temp_name)
            else:
                await interaction.followup.send(
                    f"Logs for {bot_name} (User: {user_id}):\n```\n{logs}\n```"
                )
        else:
            await interaction.followup.send(f"❌ {logs}")

    @app_commands.command(name="kill", description="Force stop a bot (admin only)")
    async def kill(self, interaction: discord.Interaction, user_id: str, bot_name: str):
        await interaction.response.defer(thinking=True)
        if not self.bot.is_admin(interaction):
            await interaction.followup.send("❌ You don't have permission to use admin commands", ephemeral=True)
            return

        try:
            all_bots = self.bot.container_manager.active_bots.get(user_id, {})
            if bot_name not in all_bots:
                await interaction.followup.send(f"❌ Bot {bot_name} not found for user {user_id}")
                return

            container_id = all_bots[bot_name]["container_id"]
            container = self.bot.container_manager.docker_client.containers.get(container_id)
            container.kill()

            await self.bot.refresh_bot_list()
            await interaction.followup.send(f"✅ Bot {bot_name} forcefully stopped")
        except Exception as e:
            self.bot.logger.error(f"Error killing bot: {e}")
            await interaction.followup.send(f"❌ Error killing bot: {str(e)}")

    @app_commands.command(name="delete", description="Delete any bot (admin only)")
    async def delete(self, interaction: discord.Interaction, user_id: str, bot_name: str):
        await interaction.response.defer(thinking=True)
        if not self.bot.is_admin(interaction):
            await interaction.followup.send("❌ You don't have permission to use admin commands", ephemeral=True)
            return

        success, message = await self.bot.delete_bot(user_id, bot_name)
        if success:
            await interaction.followup.send(f"✅ {message}")
        else:
            await interaction.followup.send(f"❌ {message}")

    @app_commands.command(name="add-admin", description="Add a user to admin list (admin only)")
    async def add_admin(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(thinking=True)
        if not self.bot.is_admin(interaction):
            await interaction.followup.send("❌ You don't have permission to use admin commands", ephemeral=True)
            return

        try:
            try:
                user = await self.bot.fetch_user(int(user_id))
            except Exception:
                await interaction.followup.send(f"❌ Invalid user ID: {user_id}")
                return

            if user_id not in self.bot.config["admin_users"]:
                self.bot.config["admin_users"].append(user_id)
                self.bot.save_config()
                await interaction.followup.send(f"✅ Added {user.name} ({user_id}) to admin list")
            else:
                await interaction.followup.send(f"User {user.name} ({user_id}) is already an admin")
        except Exception as e:
            self.bot.logger.error(f"Error adding admin: {e}")
            await interaction.followup.send(f"❌ Error adding admin: {str(e)}")

    @app_commands.command(name="remove-admin", description="Remove a user from admin list (admin only)")
    async def remove_admin(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(thinking=True)
        if not self.bot.is_admin(interaction):
            await interaction.followup.send("❌ You don't have permission to use admin commands", ephemeral=True)
            return

        try:
            if user_id in self.bot.config["admin_users"]:
                self.bot.config["admin_users"].remove(user_id)
                self.bot.save_config()
                await interaction.followup.send(f"✅ Removed user {user_id} from admin list")
            else:
                await interaction.followup.send(f"User {user_id} is not in the admin list")
        except Exception as e:
            self.bot.logger.error(f"Error removing admin: {e}")
            await interaction.followup.send(f"❌ Error removing admin: {str(e)}")

    @app_commands.command(name="set-limit", description="Set max bots per user (admin only)")
    async def set_limit(self, interaction: discord.Interaction, limit: int):
        await interaction.response.defer(thinking=True)
        if not self.bot.is_admin(interaction):
            await interaction.followup.send("❌ You don't have permission to use admin commands", ephemeral=True)
            return

        try:
            if limit < 1:
                await interaction.followup.send("❌ Limit must be at least 1")
                return

            old_limit = self.bot.config["max_bots_per_user"]
            self.bot.config["max_bots_per_user"] = limit
            self.bot.save_config()

            await interaction.followup.send(f"✅ Updated max bots per user from {old_limit} to {limit}")
        except Exception as e:
            self.bot.logger.error(f"Error setting limit: {e}")
            await interaction.followup.send(f"❌ Error setting limit: {str(e)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot))