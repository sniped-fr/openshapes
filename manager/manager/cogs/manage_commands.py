import discord
from discord import app_commands
from discord.ext import commands

class ManageCommands(commands.GroupCog, group_name="manage", group_description="Manage your OpenShapes bots"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="list", description="List your OpenShapes bots")
    async def list_bots(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        user_bots = self.bot.get_user_bots(user_id)

        if not user_bots:
            await interaction.followup.send("You don't have any OpenShapes bots yet. Use `/create bot` to create one.")
            return

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

    @app_commands.command(name="start", description="Start a stopped bot")
    async def start_bot(self, interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        success, message = await self.bot.start_bot(user_id, bot_name)

        if success:
            await interaction.followup.send(f"✅ {message}")
        else:
            await interaction.followup.send(f"❌ {message}")

    @app_commands.command(name="stop", description="Stop a running bot")
    async def stop_bot(self, interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        success, message = await self.bot.stop_bot(user_id, bot_name)

        if success:
            await interaction.followup.send(f"✅ {message}")
        else:
            await interaction.followup.send(f"❌ {message}")

    @app_commands.command(name="restart", description="Restart a bot")
    async def restart_bot(self, interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        success, message = await self.bot.restart_bot(user_id, bot_name)

        if success:
            await interaction.followup.send(f"✅ {message}")
        else:
            await interaction.followup.send(f"❌ {message}")

    @app_commands.command(name="delete", description="Delete a bot completely")
    async def delete_bot(self, interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)

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
                await button_interaction.response.send_message("This is not your confirmation dialog", ephemeral=True)
                return
            success, message = await self.bot.delete_bot(user_id, bot_name)
            if success:
                await button_interaction.response.edit_message(content=f"✅ {message}", view=None)
            else:
                await button_interaction.response.edit_message(content=f"❌ {message}", view=None)

        async def cancel_callback(button_interaction: discord.Interaction):
            if button_interaction.user.id != interaction.user.id:
                await button_interaction.response.send_message("This is not your confirmation dialog", ephemeral=True)
                return
            await button_interaction.response.edit_message(content="Delete operation canceled", view=None)

        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)

        await interaction.followup.send(
            f"⚠️ Are you sure you want to delete the bot '{bot_name}'? This action cannot be undone.",
            view=confirm_view,
        )

    @app_commands.command(name="logs", description="Get logs from a bot")
    async def logs(self, interaction: discord.Interaction, bot_name: str, lines: int = 20):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        success, logs = await self.bot.get_bot_logs(user_id, bot_name, lines)

        if success:
            if len(logs) > 1950:
                logs = logs[-1950:] + "...(truncated)"
            await interaction.followup.send(f"```\n{logs}\n```")
        else:
            await interaction.followup.send(f"❌ {logs}")

    @app_commands.command(name="status", description="Get detailed status of a bot")
    async def status(self, interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        success, stats = await self.bot.get_bot_stats(user_id, bot_name)

        if success and stats:
            embed = discord.Embed(
                title=f"Bot Status: {bot_name}",
                color=(discord.Color.green() if stats["status"] == "running" else discord.Color.red()),
            )
            embed.add_field(name="Status", value=stats["status"], inline=True)
            embed.add_field(name="Uptime", value=stats["uptime"], inline=True)
            embed.add_field(name="Container ID", value=stats["container_id"], inline=True)
            embed.add_field(name="CPU Usage", value=stats["cpu_percent"], inline=True)
            embed.add_field(name="Memory Usage", value=stats["memory_usage"], inline=True)
            embed.add_field(name="Memory %", value=stats["memory_percent"], inline=True)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ Could not retrieve stats for bot {bot_name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ManageCommands(bot))