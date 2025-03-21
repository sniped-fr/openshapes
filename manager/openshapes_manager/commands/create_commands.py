import discord
from typing import Optional

def setup_create_commands(bot, create_commands):
    @create_commands.command(name="bot", description="Create a new OpenShapes bot")
    async def create_bot_command(
        interaction: discord.Interaction,
        bot_name: str,
        bot_token: str,
        config_file: discord.Attachment,
        brain_file: Optional[discord.Attachment] = None,
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)
        user_id = str(interaction.user.id)

        try:
            config_content = await config_file.read()
            config_json = config_content.decode("utf-8")

            brain_json = None
            if brain_file:
                brain_content = await brain_file.read()
                brain_json = brain_content.decode("utf-8")

            success, message = await bot.create_bot(
                user_id, bot_name, config_json, bot_token, brain_json
            )

            if success:
                await interaction.followup.send(f"✅ {message}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ {message}", ephemeral=True)

        except Exception as e:
            bot.logger.error(f"Error in create_bot_command: {e}")
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}", ephemeral=True
            )