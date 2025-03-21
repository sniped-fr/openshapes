import discord
from typing import Optional, Any


class CommandResult:
    def __init__(self, success: bool, message: str, data: Any = None):
        self.success = success
        self.message = message
        self.data = data


class FileProcessor:
    @staticmethod
    async def process_attachment(attachment: discord.Attachment) -> str:
        content = await attachment.read()
        return content.decode("utf-8")


class BotCreationCommand:
    def __init__(self, bot):
        self.bot = bot
    
    async def execute(
        self,
        interaction: discord.Interaction,
        bot_name: str,
        bot_token: str,
        config_file: discord.Attachment,
        brain_file: Optional[discord.Attachment] = None
    ) -> CommandResult:
        try:
            user_id = str(interaction.user.id)

            config_json = await FileProcessor.process_attachment(config_file)

            brain_json = None
            if brain_file:
                brain_json = await FileProcessor.process_attachment(brain_file)

            success, message = await self.bot.create_bot(
                user_id, bot_name, config_json, bot_token, brain_json
            )
            
            return CommandResult(success, message)
            
        except Exception as e:
            self.bot.logger.error(f"Error in bot creation command: {e}")
            return CommandResult(False, f"An error occurred: {str(e)}")


class CreateCommandsManager:
    def __init__(self, bot):
        self.bot = bot
        self.commands = {
            "bot": BotCreationCommand(bot)
        }
    
    async def handle_command_response(
        self, interaction: discord.Interaction, result: CommandResult
    ) -> None:
        if result.success:
            await interaction.followup.send(f"✅ {result.message}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ {result.message}", ephemeral=True)


def setup_create_commands(bot, create_commands):
    manager = CreateCommandsManager(bot)
    
    @create_commands.command(name="bot", description="Create a new OpenShapes bot")
    async def create_bot_command(
        interaction: discord.Interaction,
        bot_name: str,
        bot_token: str,
        config_file: discord.Attachment,
        brain_file: Optional[discord.Attachment] = None,
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        command = manager.commands["bot"]
        result = await command.execute(
            interaction, bot_name, bot_token, config_file, brain_file
        )
        
        await manager.handle_command_response(interaction, result)
