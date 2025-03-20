import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import aiohttp
import json
import math
import re

class SearchModal(discord.ui.Modal):
    def __init__(self, title="Search Models"):
        super().__init__(title=title)
        
        self.search_input = discord.ui.TextInput(
            label="Search Term",
            placeholder="Enter model name to search",
            required=False,
            max_length=100
        )
        self.add_item(self.search_input)

class ModelSelectView(discord.ui.View):
    def __init__(self, bot, all_models, filtered_models=None, search_term="", page=0, interaction=None, timeout=180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.all_models = all_models
        self.filtered_models = filtered_models or all_models
        self.search_term = search_term
        self.page = page
        self.models_per_page = 25
        self.max_pages = math.ceil(len(self.filtered_models) / self.models_per_page)
        self.original_interaction = interaction
        
        # Add search button
        self.add_search_button()
        
        # Add page navigation buttons
        self.update_buttons()
        
        # Add model selection dropdown for current page
        self.update_dropdown()
    
    def add_search_button(self):
        search_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="🔍 Search Models",
            custom_id="search_models"
        )
        search_button.callback = self.show_search_modal
        self.add_item(search_button)
    
    async def show_search_modal(self, interaction):
        """Show search modal when search button is clicked"""
        search_modal = SearchModal()
        
        async def on_submit(modal_interaction):
            search_term = search_modal.search_input.value.strip().lower()
            
            # Filter models based on search term
            if search_term:
                filtered_models = [
                    model for model in self.all_models 
                    if search_term in model.get('id', '').lower()
                ]
            else:
                filtered_models = self.all_models
            
            # Create new view with filtered models
            new_view = ModelSelectView(
                self.bot, 
                self.all_models,
                filtered_models,
                search_term,
                0,  # Reset to first page
                self.original_interaction
            )
            
            # Create embed for the filtered results
            embed = new_view.create_embed()
            
            await modal_interaction.response.edit_message(embed=embed, view=new_view)
            
        search_modal.on_submit = on_submit
        await interaction.response.send_modal(search_modal)
    
    def update_buttons(self):
        # Clear existing pagination buttons
        for item in list(self.children):
            if isinstance(item, discord.ui.Button) and item.custom_id in ["previous_page", "next_page"]:
                self.remove_item(item)
        
        # Add navigation buttons
        previous_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="◀️ Previous",
            disabled=self.page <= 0,
            custom_id="previous_page",
            row=1
        )
        previous_button.callback = self.previous_page
        
        next_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Next ▶️",
            disabled=self.page >= self.max_pages - 1,
            custom_id="next_page",
            row=1
        )
        next_button.callback = self.next_page
        
        self.add_item(previous_button)
        self.add_item(next_button)
    
    def update_dropdown(self):
        # Clear existing dropdown
        for item in list(self.children):
            if isinstance(item, discord.ui.Select) and item.custom_id == "model_select":
                self.remove_item(item)
        
        # If no models to display, add a placeholder dropdown
        if not self.filtered_models:
            select = discord.ui.Select(
                placeholder="No models found matching your search",
                options=[discord.SelectOption(label="No results", value="none")],
                disabled=True,
                custom_id="model_select",
                row=2
            )
            self.add_item(select)
            return
        
        # Calculate start and end indices for current page
        start_idx = self.page * self.models_per_page
        end_idx = min(start_idx + self.models_per_page, len(self.filtered_models))
        
        # Create options for dropdown
        options = []
        for i in range(start_idx, end_idx):
            model = self.filtered_models[i]
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
            custom_id="model_select",
            row=2
        )
        select.callback = self.model_selected
        self.add_item(select)
    
    async def previous_page(self, interaction):
        """Go to the previous page of models"""
        self.page = max(0, self.page - 1)
        self.update_buttons()
        self.update_dropdown()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_page(self, interaction):
        """Go to the next page of models"""
        self.page = min(self.max_pages - 1, self.page + 1)
        self.update_buttons()
        self.update_dropdown()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def model_selected(self, interaction):
        """Handle model selection from dropdown"""
        # Get the selected model
        selected_model = interaction.data['values'][0]
        
        # Update the bot's configuration
        old_model = self.bot.chat_model
        self.bot.chat_model = selected_model
        self.bot.api_settings["chat_model"] = selected_model
        
        # Save the configuration
        self.bot.config_manager.update_field("api_settings", self.bot.api_settings)
        
        # Create a confirmation message
        embed = discord.Embed(
            title="Model Updated",
            description=f"Changed model from `{old_model}` to `{selected_model}`",
            color=discord.Color.green()
        )
        
        # Create a new view that has the updated selection
        new_view = ModelSelectView(
            self.bot, 
            self.all_models,
            self.filtered_models,
            self.search_term,
            self.page,
            self.original_interaction
        )
        
        await interaction.response.edit_message(embed=embed, view=new_view)
    
    def create_embed(self):
        """Create the embed for the model selection interface"""
        if self.search_term:
            title = f"Models matching '{self.search_term}'"
        else:
            title = "Available Models"
            
        embed = discord.Embed(
            title=title,
            description=f"Page {self.page + 1}/{max(1, self.max_pages)} • {len(self.filtered_models)} models available",
            color=discord.Color.blue()
        )
        
        # Add current model info
        embed.add_field(
            name="Current Model",
            value=f"`{self.bot.chat_model}`",
            inline=False
        )
        
        # Add search instructions if not searching
        if not self.search_term:
            embed.add_field(
                name="Search",
                value="Click the 🔍 button to search for specific models",
                inline=False
            )
        # Or add reset instructions if already searching
        elif len(self.filtered_models) == 0:
            embed.add_field(
                name="No Results",
                value="No models found matching your search. Try a different search term.",
                inline=False
            )
        
        return embed
    
    async def on_timeout(self):
        """Handle view timeout"""
        # Disable all items when the view times out
        for item in self.children:
            item.disabled = True
        
        if self.original_interaction:
            try:
                # Update the message with disabled components
                embed = discord.Embed(
                    title="Model Selection Timed Out",
                    description="This selection has expired. Please run the command again to select a model.",
                    color=discord.Color.red()
                )
                await self.original_interaction.edit_original_response(embed=embed, view=self)
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
                            if "/v1/chat/completions" in endpoints or "chat.completions" in endpoints:
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


async def model_command(bot, interaction, search_term=None):
    """Handle the model selection command"""
    if interaction.user.id != bot.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can change the model.", ephemeral=True
        )
        return
    
    # Defer the response since model fetching might take some time
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    # Fetch available models
    all_models = await fetch_available_models(bot)
    
    if not all_models:
        await interaction.followup.send(
            "Could not fetch models. Please check your API settings and try again.",
            ephemeral=True
        )
        return
    
    # Filter models by search term if provided
    if search_term:
        search_term = search_term.lower()
        filtered_models = [model for model in all_models if search_term in model.get('id', '').lower()]
    else:
        filtered_models = all_models
    
    # Create the model selection view
    view = ModelSelectView(
        bot, 
        all_models, 
        filtered_models, 
        search_term or "", 
        interaction=interaction
    )
    embed = view.create_embed()
    
    # Send the response
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)