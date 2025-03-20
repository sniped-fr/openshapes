import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import aiohttp
import json
import math

class ModelSelectView(discord.ui.View):
    def __init__(self, bot, models, page=0, interaction=None, timeout=60):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.models = models
        self.page = page
        self.models_per_page = 25
        self.max_pages = math.ceil(len(models) / self.models_per_page)
        self.original_interaction = interaction
        
        # Add page navigation buttons
        self.update_buttons()
        
        # Add model selection dropdown for current page
        self.update_dropdown()
    
    def update_buttons(self):
        # Clear existing buttons
        for item in list(self.children):
            if isinstance(item, discord.ui.Button):
                self.remove_item(item)
        
        # Add navigation buttons
        previous_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Previous Page",
            disabled=self.page <= 0,
            custom_id="previous_page"
        )
        previous_button.callback = self.previous_page
        
        next_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Next Page",
            disabled=self.page >= self.max_pages - 1,
            custom_id="next_page"
        )
        next_button.callback = self.next_page
        
        self.add_item(previous_button)
        self.add_item(next_button)
    
    def update_dropdown(self):
        # Clear existing dropdown
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        
        # Calculate start and end indices for current page
        start_idx = self.page * self.models_per_page
        end_idx = min(start_idx + self.models_per_page, len(self.models))
        
        # Create options for dropdown
        options = []
        for i in range(start_idx, end_idx):
            model = self.models[i]
            model_id = model.get('id', 'unknown')
            
            # Check if this is the currently selected model
            is_default = model_id == self.bot.chat_model
            
            # Create a descriptive label
            label = f"{model_id}"
            if len(label) > 100:  # Discord has a 100 char limit for labels
                label = label[:97] + "..."
                
            # Add option to dropdown
            options.append(
                discord.SelectOption(
                    label=label,
                    value=model_id,
                    default=is_default
                )
            )
        
        # Create and add the dropdown
        select = discord.ui.Select(
            placeholder="Select a model",
            options=options,
            custom_id="model_select"
        )
        select.callback = self.model_selected
        self.add_item(select)
    
    async def previous_page(self, interaction):
        self.page = max(0, self.page - 1)
        self.update_buttons()
        self.update_dropdown()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_page(self, interaction):
        self.page = min(self.max_pages - 1, self.page + 1)
        self.update_buttons()
        self.update_dropdown()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def model_selected(self, interaction):
        # Get the selected model
        selected_model = interaction.data['values'][0]
        
        # Update the bot's configuration
        old_model = self.bot.chat_model
        self.bot.chat_model = selected_model
        self.bot.api_settings["chat_model"] = selected_model
        
        # Save the configuration
        self.bot.config_manager.update_field("api_settings", self.bot.api_settings)
        
        # Update the UI to reflect the selection
        self.update_dropdown()  # This will mark the newly selected model as default
        
        # Create a confirmation message
        embed = discord.Embed(
            title="Model Updated",
            description=f"Changed model from `{old_model}` to `{selected_model}`",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    def create_embed(self):
        embed = discord.Embed(
            title="Select a model",
            description=f"Page {self.page + 1}/{self.max_pages}",
            color=discord.Color.blue()
        )
        
        # Add current model info
        embed.add_field(
            name="Current Model",
            value=f"`{self.bot.chat_model}`",
            inline=False
        )
        
        return embed
    
    async def on_timeout(self):
        # Disable all items when the view times out
        for item in self.children:
            item.disabled = True
        
        if self.original_interaction:
            try:
                await self.original_interaction.edit_original_response(view=self)
            except:
                pass


async def fetch_available_models(bot):
    """Fetch available models from the API"""
    if not bot.base_url or not bot.api_key:
        return []
    
    try:
        url = f"{bot.base_url}/models"
        
        # Set up headers with API key
        headers = {
            "Authorization": f"Bearer {bot.api_key}",
            "Content-Type": "application/json"
        }
        
        # Make the request
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract the models from the response
                    if "data" in data and isinstance(data["data"], list):
                        # Filter models that support chat completions
                        chat_models = []
                        for model in data["data"]:
                            # Check if the model supports chat completions
                            endpoints = model.get("endpoints", model.get("endpoint", []))
                            if "/v1/chat/completions" in endpoints or "/v1/chat/generate" in endpoints:
                                chat_models.append(model)
                        
                        return chat_models
                    
                    return []
                else:
                    error_text = await response.text()
                    print(f"Error fetching models: {error_text}")
                    return []
    except Exception as e:
        print(f"Exception fetching models: {e}")
        return []


async def model_command(bot, interaction):
    """Handle the model selection command"""
    if interaction.user.id != bot.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can change the model.", ephemeral=True
        )
        return
    
    # Defer the response since model fetching might take some time
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    # Fetch available models
    models = await fetch_available_models(bot)
    
    if not models:
        await interaction.followup.send(
            "Could not fetch models. Please check your API settings and try again.",
            ephemeral=True
        )
        return
    
    # Create the model selection view
    view = ModelSelectView(bot, models, interaction=interaction)
    embed = view.create_embed()
    
    # Send the response
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)