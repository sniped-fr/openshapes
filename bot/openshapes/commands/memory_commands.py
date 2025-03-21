import discord
import logging
from typing import Any, Protocol

logger = logging.getLogger("openshape")

class CommandExecutor(Protocol):
    @staticmethod
    async def execute(bot: Any, interaction: discord.Interaction) -> None:
        pass

class MemoryCommandHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def handle_sleep(self, interaction: discord.Interaction) -> None:
        from vectordb.chroma_integration import SleepCommand
        await SleepCommand.execute(self.bot, interaction)
        
    async def handle_memory(self, interaction: discord.Interaction) -> None:
        from vectordb.chroma_integration import MemoryCommand
        await MemoryCommand.execute(self.bot, interaction)

async def sleep_command(self, interaction: discord.Interaction) -> None:
    handler = MemoryCommandHandler(self)
    await handler.handle_sleep(interaction)

async def memory_command(self, interaction: discord.Interaction) -> None:
    handler = MemoryCommandHandler(self)
    await handler.handle_memory(interaction)
