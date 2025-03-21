import discord
from discord import ui
import logging
from typing import List, Dict

logger = logging.getLogger("openshape")

class ModelSelectView(ui.View):
    def __init__(self, bot, models: List[Dict[str, str]], timeout: int = 60):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.models = models
        
        for model in models[:25]:
            button = ui.Button(
                label=model["name"], 
                style=discord.ButtonStyle.secondary,
                custom_id=model["id"]
            )
            button.callback = self.button_callback
            self.add_item(button)
    
    async def button_callback(self, interaction: discord.Interaction):
        selected_model_id = interaction.data["custom_id"]
        selected_model = next((m for m in self.models if m["id"] == selected_model_id), None)
        
        if not selected_model:
            await interaction.response.send_message("Error: Model not found", ephemeral=True)
            return

        self.bot.chat_model = selected_model["id"]
        self.bot.api_settings["chat_model"] = selected_model["id"]
        self.bot.config_manager.save_config()
        
        await interaction.response.send_message(
            f"AI model switched to: **{selected_model['name']}**", ephemeral=True
        )

        embed = discord.Embed(
            title="Model Selection",
            description=f"Current model: **{selected_model['name']}**",
            color=discord.Color.green()
        )
        await interaction.message.edit(embed=embed, view=None)

async def fetch_available_models(bot) -> List[Dict[str, str]]:
    if not bot.ai_client:
        logger.warning("No AI client configured, can't fetch models")
        return []
        
    try:
        response = await bot.ai_client.models.list()
        models = []
        
        for model in response.data:
            if "chat" not in model.id.lower() and "instruct" not in model.id.lower():
                continue
                
            models.append({
                "id": model.id,
                "name": model.id.split("/")[-1] if "/" in model.id else model.id,
                "description": getattr(model, "description", "")
            })
            
        return models
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return []

async def model_command(bot, interaction: discord.Interaction):
    if interaction.user.id != bot.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can change the AI model", ephemeral=True
        )
        return
        
    if not bot.ai_client:
        await interaction.response.send_message(
            "AI client not configured. Set API settings first.", ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    models = await fetch_available_models(bot)
    
    if not models:
        await interaction.followup.send(
            "No models found or couldn't fetch models from API.", ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="Select AI Model",
        description=f"Current model: **{bot.chat_model}**\nChoose a model to use:",
        color=discord.Color.blue()
    )
    
    view = ModelSelectView(bot, models)
    
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
