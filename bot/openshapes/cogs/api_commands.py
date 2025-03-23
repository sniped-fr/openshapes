import logging
import discord
from discord.ext import commands
from openai import AsyncOpenAI
from openshapes.views import APISettingModal

logger = logging.getLogger("openshape")

class APISettingsHandler:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handle_api_command(self, interaction: discord.Interaction) -> None:
        if str(interaction.user.id) != self.bot.config_manager.get("owner_id"):
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        options = [
            discord.SelectOption(label="View Current Settings", value="view"),
            discord.SelectOption(label="Set Base URL", value="base_url"),
            discord.SelectOption(label="Set API Key", value="api_key"),
            discord.SelectOption(label="Set Chat Model", value="chat_model"),
            discord.SelectOption(label="Set TTS Model", value="tts_model"),
            discord.SelectOption(label="Set TTS Voice", value="tts_voice"),
            discord.SelectOption(label="Toggle TTS", value="toggle_tts"),
            discord.SelectOption(label="Test Connection", value="test"),
        ]

        select = discord.ui.Select(placeholder="Select API Setting", options=options)
        select.callback = self.select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            "Configure API Settings:", view=view, ephemeral=True
        )

    async def select_callback(self, select_interaction: discord.Interaction) -> None:
        action = select_interaction.data['values'][0]

        if action == "view":
            await self.view_settings(select_interaction)
        elif action == "toggle_tts":
            await self.toggle_tts(select_interaction)
        elif action == "test":
            await self.test_connection(select_interaction)
        else:
            await self.update_setting(select_interaction, action)

    async def view_settings(self, interaction: discord.Interaction) -> None:
        masked_key = "••••••" + self.bot.api_integration.api_key[-4:] if self.bot.api_integration.api_key else "Not set"
        settings_info = "**API Settings:**\n"
        settings_info += f"- Base URL: {self.bot.api_integration.base_url or 'Not set'}\n"
        settings_info += f"- API Key: {masked_key}\n"
        settings_info += f"- Chat Model: {self.bot.api_integration.chat_model or 'Not set'}\n"
        settings_info += f"- TTS Model: {self.bot.api_integration.tts_model or 'Not set'}\n"
        settings_info += f"- TTS Voice: {self.bot.api_integration.tts_voice or 'Not set'}\n"
        settings_info += f"- TTS Enabled: {'Yes' if self.bot.use_tts else 'No'}"

        await interaction.response.send_message(settings_info, ephemeral=True)

    async def toggle_tts(self, interaction: discord.Interaction) -> None:
        self.bot.use_tts = not self.bot.use_tts
        self.bot.config_manager.update_field("use_tts", self.bot.use_tts)
        await interaction.response.send_message(
            f"TTS has been {'enabled' if self.bot.use_tts else 'disabled'}",
            ephemeral=True,
        )

    async def test_connection(self, interaction: discord.Interaction) -> None:
        if not self.bot.api_integration.client or not self.bot.api_integration.api_key or not self.bot.api_integration.base_url or not self.bot.api_integration.chat_model:
            await interaction.response.send_message(
                "Cannot test API connection: Missing required API settings",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            response = await self.bot.api_integration.client.chat.completions.create(
                model=self.bot.api_integration.chat_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello, this is a test message."}
                ],
                max_tokens=50
            )

            if response and response.choices and response.choices[0].message.content:
                await interaction.followup.send(
                    f"API connection successful!\nTest response: {response.choices[0].message.content[:100]}...",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "API test failed: No response received", ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                f"API test failed: {str(e)}", ephemeral=True
            )

    async def update_setting(self, interaction: discord.Interaction, action: str) -> None:
        modal = APISettingModal(title=f"Set {action.replace('_', ' ').title()}")

        async def on_submit(modal_interaction: discord.Interaction):
            value = modal.setting_input.value
            setattr(self.bot.api_integration, action, value)
            self.bot.config_manager.update_field("api_settings", self.bot.api_integration)

            if self.bot.api_integration.api_key and self.bot.api_integration.base_url:
                try:
                    self.bot.api_integration.client = AsyncOpenAI(
                        api_key=self.bot.api_integration.api_key,
                        base_url=self.bot.api_integration.base_url,
                        max_retries=2,
                        timeout=60,
                    )
                    await modal_interaction.response.send_message(
                        f"{action.replace('_', ' ').title()} updated and client reinitialized!",
                        ephemeral=True,
                    )
                except Exception as e:
                    await modal_interaction.response.send_message(
                        f"{action.replace('_', ' ').title()} updated but client initialization failed: {e}",
                        ephemeral=True,
                    )
            else:
                await modal_interaction.response.send_message(
                    f"{action.replace('_', ' ').title()} updated!",
                    ephemeral=True,
                )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

class APICommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="api_settings", description="Configure API settings")
    async def api_settings(self, interaction: discord.Interaction) -> None:
        handler = APISettingsHandler(self.bot)
        await handler.handle_api_command(interaction)

async def setup(bot: commands.Bot):
    await bot.add_cog(APICommandsCog(bot))