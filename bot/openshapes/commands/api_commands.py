import discord
from openshapes.utils.views import APISettingModal
import logging
from openai import AsyncOpenAI

logger = logging.getLogger("openshape")

async def api_settings_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
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

    async def select_callback(select_interaction):
        action = select.values[0]

        if action == "view":
            masked_key = "••••••" + self.api_key[-4:] if self.api_key else "Not set"
            settings_info = "**API Settings:**\n"
            settings_info += f"- Base URL: {self.base_url or 'Not set'}\n"
            settings_info += f"- API Key: {masked_key}\n"
            settings_info += f"- Chat Model: {self.chat_model or 'Not set'}\n"
            settings_info += f"- TTS Model: {self.tts_model or 'Not set'}\n"
            settings_info += f"- TTS Voice: {self.tts_voice or 'Not set'}\n"
            settings_info += f"- TTS Enabled: {'Yes' if self.use_tts else 'No'}"

            await select_interaction.response.send_message(
                settings_info, ephemeral=True
            )

        elif action == "toggle_tts":
            self.use_tts = not self.use_tts
            self.config_manager.update_field("use_tts", self.use_tts)
            await select_interaction.response.send_message(
                f"TTS has been {'enabled' if self.use_tts else 'disabled'}",
                ephemeral=True,
            )

        elif action == "test":
            if (
                not self.ai_client
                or not self.api_key
                or not self.base_url
                or not self.chat_model
            ):
                await select_interaction.response.send_message(
                    "Cannot test API connection: Missing required API settings",
                    ephemeral=True,
                )
                return

            await select_interaction.response.defer(ephemeral=True)

            try:
                response = await self.ai_client.chat.completions.create(
                    model=self.chat_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Hello, this is a test message."}
                    ],
                    max_tokens=50
                )

                if response and response.choices and response.choices[0].message.content:
                    await select_interaction.followup.send(
                        f"API connection successful!\nTest response: {response.choices[0].message.content[:100]}...",
                        ephemeral=True,
                    )
                else:
                    await select_interaction.followup.send(
                        "API test failed: No response received", ephemeral=True
                    )
            except Exception as e:
                await select_interaction.followup.send(
                    f"API test failed: {str(e)}", ephemeral=True
                )

        else:
            modal = APISettingModal(title=f"Set {action.replace('_', ' ').title()}")

            async def on_submit(modal_interaction):
                value = modal.setting_input.value

                if action == "base_url":
                    self.base_url = value
                    self.api_settings["base_url"] = value
                elif action == "api_key":
                    self.api_key = value
                    self.api_settings["api_key"] = value
                elif action == "chat_model":
                    self.chat_model = value
                    self.api_settings["chat_model"] = value
                elif action == "tts_model":
                    self.tts_model = value
                    self.api_settings["tts_model"] = value
                elif action == "tts_voice":
                    self.tts_voice = value
                    self.api_settings["tts_voice"] = value

                self.config_manager.update_field("api_settings", self.api_settings)

                if self.api_key and self.base_url:
                    try:
                        self.ai_client = AsyncOpenAI(
                            api_key=self.api_key,
                            base_url=self.base_url,
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
            await select_interaction.response.send_modal(modal)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)

    await interaction.response.send_message(
        "Configure API Settings:", view=view, ephemeral=True
    )
