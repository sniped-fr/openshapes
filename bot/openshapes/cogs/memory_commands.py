import logging
import discord
from typing import Protocol
from discord.ext import commands
from openshapes.vectordb.chroma_integration import SleepCommand, MemoryCommand

logger = logging.getLogger("openshape")

class CommandExecutor(Protocol):
    @staticmethod
    async def execute(bot: commands.Bot, interaction: discord.Interaction) -> None:
        pass

class MemoryCommandHandler:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    async def handle_sleep(self, interaction: discord.Interaction) -> None:
        await SleepCommand.execute(self.bot, interaction)
        
    async def handle_memory(self, interaction: discord.Interaction) -> None:
        await MemoryCommand.execute(self.bot, interaction)

class MemoryCommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="sleep", description="Process conversations into long-term memory")
    async def sleep(self, interaction: discord.Interaction) -> None:
        handler = MemoryCommandHandler(self.bot)
        await handler.handle_sleep(interaction)

    @discord.app_commands.command(name="memory", description="Manage bot memory")
    async def memory(self, interaction: discord.Interaction) -> None:
        handler = MemoryCommandHandler(self.bot)
        await handler.handle_memory(interaction)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemoryCommandsCog(bot))
