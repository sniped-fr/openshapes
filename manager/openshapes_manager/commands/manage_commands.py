import discord
from typing import Dict, Any, Tuple


class CommandResult:
    def __init__(self, success: bool, message: str, data: Any = None):
        self.success = success
        self.message = message
        self.data = data


class BotManageCommand:
    def __init__(self, bot):
        self.bot = bot
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> CommandResult:
        try:
            result = await self._execute_command(interaction, **kwargs)
            return result
        except Exception as e:
            self.bot.logger.error(f"Error in manage command: {e}")
            return CommandResult(False, f"An error occurred: {str(e)}")
    
    async def _execute_command(self, interaction: discord.Interaction, **kwargs) -> CommandResult:
        raise NotImplementedError("Subclasses must implement _execute_command")


class ListBotsCommand(BotManageCommand):
    async def _execute_command(self, interaction: discord.Interaction, **kwargs) -> CommandResult:
        user_id = str(interaction.user.id)
        user_bots = self.bot.get_user_bots(user_id)
        
        if not user_bots:
            return CommandResult(True, "You don't have any OpenShapes bots yet. Use `/create bot` to create one.")
        
        embed = await self._create_bots_embed(user_bots)
        return CommandResult(True, "", embed)
    
    async def _create_bots_embed(self, user_bots: Dict[str, Dict[str, Any]]) -> discord.Embed:
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
        
        return embed


class BotActionCommand(BotManageCommand):
    async def _execute_command(
        self, interaction: discord.Interaction, bot_name: str, **kwargs
    ) -> CommandResult:
        user_id = str(interaction.user.id)
        
        success, message = await self._perform_bot_action(user_id, bot_name)
        return CommandResult(success, message)
    
    async def _perform_bot_action(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        raise NotImplementedError("Subclasses must implement _perform_bot_action")


class StartBotCommand(BotActionCommand):
    async def _perform_bot_action(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        return await self.bot.start_bot(user_id, bot_name)


class StopBotCommand(BotActionCommand):
    async def _perform_bot_action(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        return await self.bot.stop_bot(user_id, bot_name)


class RestartBotCommand(BotActionCommand):
    async def _perform_bot_action(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        return await self.bot.restart_bot(user_id, bot_name)


class DeleteConfirmationView(discord.ui.View):
    def __init__(self, bot, user_id: str, bot_name: str, original_user_id: int, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id
        self.bot_name = bot_name
        self.original_user_id = original_user_id
        self._add_buttons()
    
    def _add_buttons(self) -> None:
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
        
        confirm_button.callback = self.confirm_callback
        cancel_button.callback = self.cancel_callback
        
        self.add_item(confirm_button)
        self.add_item(cancel_button)
    
    async def confirm_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message(
                "This is not your confirmation dialog", ephemeral=True
            )
            return
        
        success, message = await self.bot.delete_bot(self.user_id, self.bot_name)
        
        if success:
            await interaction.response.edit_message(
                content=f"✅ {message}", view=None
            )
        else:
            await interaction.response.edit_message(
                content=f"❌ {message}", view=None
            )
    
    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message(
                "This is not your confirmation dialog", ephemeral=True
            )
            return
        
        await interaction.response.edit_message(
            content="Delete operation canceled", view=None
        )


class DeleteBotCommand(BotManageCommand):
    async def _execute_command(
        self, interaction: discord.Interaction, bot_name: str, **kwargs
    ) -> CommandResult:
        user_id = str(interaction.user.id)
        
        view = DeleteConfirmationView(self.bot, user_id, bot_name, interaction.user.id)
        
        return CommandResult(
            True,
            f"⚠️ Are you sure you want to delete the bot '{bot_name}'? This action cannot be undone.",
            view
        )


class LogsCommand(BotManageCommand):
    async def _execute_command(
        self, interaction: discord.Interaction, bot_name: str, lines: int = 20, **kwargs
    ) -> CommandResult:
        user_id = str(interaction.user.id)
        success, logs = await self.bot.get_bot_logs(user_id, bot_name, lines)
        
        if success:
            if len(logs) > 1950:
                logs = logs[-1950:] + "...(truncated)"
            return CommandResult(True, f"```\n{logs}\n```")
        else:
            return CommandResult(False, logs)


class StatusCommand(BotManageCommand):
    async def _execute_command(
        self, interaction: discord.Interaction, bot_name: str, **kwargs
    ) -> CommandResult:
        user_id = str(interaction.user.id)
        success, stats = await self.bot.get_bot_stats(user_id, bot_name)
        
        if success and stats:
            embed = self._create_status_embed(bot_name, stats)
            return CommandResult(True, "", embed)
        else:
            return CommandResult(False, f"Could not retrieve stats for bot {bot_name}")
    
    def _create_status_embed(self, bot_name: str, stats: Dict[str, Any]) -> discord.Embed:
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
        embed.add_field(name="Container ID", value=stats["container_id"], inline=True)
        embed.add_field(name="CPU Usage", value=stats["cpu_percent"], inline=True)
        embed.add_field(name="Memory Usage", value=stats["memory_usage"], inline=True)
        embed.add_field(name="Memory %", value=stats["memory_percent"], inline=True)
        
        return embed


class ManageCommandsManager:
    def __init__(self, bot):
        self.bot = bot
        self.commands = {
            "list": ListBotsCommand(bot),
            "start": StartBotCommand(bot),
            "stop": StopBotCommand(bot),
            "restart": RestartBotCommand(bot),
            "delete": DeleteBotCommand(bot),
            "logs": LogsCommand(bot),
            "status": StatusCommand(bot)
        }
    
    async def handle_command_response(
        self, interaction: discord.Interaction, result: CommandResult
    ) -> None:
        if isinstance(result.data, discord.Embed):
            await interaction.followup.send(embed=result.data)
        elif isinstance(result.data, discord.ui.View):
            await interaction.followup.send(result.message, view=result.data)
        elif result.success:
            if result.message:
                await interaction.followup.send(f"✅ {result.message}")
        else:
            await interaction.followup.send(f"❌ {result.message}")


def setup_manage_commands(bot, manage_commands):
    manager = ManageCommandsManager(bot)
    
    @manage_commands.command(name="list", description="List your OpenShapes bots")
    async def list_bots_command(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        command = manager.commands["list"]
        result = await command.execute(interaction)
        
        await manager.handle_command_response(interaction, result)
    
    @manage_commands.command(name="start", description="Start a stopped bot")
    async def start_bot_command(interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        
        command = manager.commands["start"]
        result = await command.execute(interaction, bot_name=bot_name)
        
        await manager.handle_command_response(interaction, result)
    
    @manage_commands.command(name="stop", description="Stop a running bot")
    async def stop_bot_command(interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        
        command = manager.commands["stop"]
        result = await command.execute(interaction, bot_name=bot_name)
        
        await manager.handle_command_response(interaction, result)
    
    @manage_commands.command(name="restart", description="Restart a bot")
    async def restart_bot_command(interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        
        command = manager.commands["restart"]
        result = await command.execute(interaction, bot_name=bot_name)
        
        await manager.handle_command_response(interaction, result)
    
    @manage_commands.command(name="delete", description="Delete a bot completely")
    async def delete_bot_command(interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        
        command = manager.commands["delete"]
        result = await command.execute(interaction, bot_name=bot_name)
        
        await manager.handle_command_response(interaction, result)
    
    @manage_commands.command(name="logs", description="Get logs from a bot")
    async def logs_bot_command(
        interaction: discord.Interaction, bot_name: str, lines: int = 20
    ):
        await interaction.response.defer(thinking=True)
        
        command = manager.commands["logs"]
        result = await command.execute(interaction, bot_name=bot_name, lines=lines)
        
        await manager.handle_command_response(interaction, result)
    
    @manage_commands.command(name="status", description="Get detailed status of a bot")
    async def status_bot_command(interaction: discord.Interaction, bot_name: str):
        await interaction.response.defer(thinking=True)
        
        command = manager.commands["status"]
        result = await command.execute(interaction, bot_name=bot_name)
        
        await manager.handle_command_response(interaction, result)
