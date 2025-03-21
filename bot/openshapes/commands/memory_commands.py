import discord
import logging

logger = logging.getLogger("openshape")

async def sleep_command(self, interaction: discord.Interaction):
    from vectordb.chroma_integration import SleepCommand
    await SleepCommand.execute(self, interaction)

async def memory_command(self, interaction: discord.Interaction):
    from vectordb.chroma_integration import MemoryCommand
    await MemoryCommand.execute(self, interaction)
