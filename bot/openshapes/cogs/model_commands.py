import math
import discord
import aiohttp
from typing import Dict, List, Optional, Any, TypedDict
from discord import app_commands
from discord.ext import commands

class ModelData(TypedDict):
    id: str
    endpoints: List[str]

class SearchModal(discord.ui.Modal):
    search_input: discord.ui.TextInput

    def __init__(self, title: str = "Search Models") -> None:
        super().__init__(title=title)
        self.search_input = discord.ui.TextInput(
            label="Search Term",
            placeholder="Enter model name to search",
            required=False,
            max_length=100
        )
        self.add_item(self.search_input)

class ModelSelectDropdown(discord.ui.Select):
    def __init__(self, parent_view: 'ModelSelectView', options: List[discord.SelectOption], is_empty: bool = False) -> None:
        if is_empty:
            super().__init__(
                placeholder="No models found matching your search",
                options=[discord.SelectOption(label="No results", value="none")],
                disabled=True,
                custom_id="model_select",
                row=2
            )
        else:
            super().__init__(
                placeholder="Select a model",
                options=options,
                custom_id="model_select",
                row=2
            )
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction) -> None:
        selected_model = interaction.data['values'][0]
        
        old_model = self.parent_view.bot.chat_model
        self.parent_view.bot.chat_model = selected_model
        self.parent_view.bot.api_settings["chat_model"] = selected_model
        self.parent_view.bot.config_manager.update_field("api_settings", self.parent_view.bot.api_settings)
        
        embed = discord.Embed(
            title="Model Updated",
            description=f"Changed model from `{old_model}` to `{selected_model}`",
            color=discord.Color.green()
        )
        
        new_view = ModelSelectView(
            self.parent_view.bot, 
            self.parent_view.all_models,
            self.parent_view.filtered_models,
            self.parent_view.search_term,
            self.parent_view.page,
            self.parent_view.original_interaction
        )
        
        await interaction.response.edit_message(embed=embed, view=new_view)

class NavigationButton(discord.ui.Button):
    def __init__(self, parent_view: 'ModelSelectView', is_next: bool = False) -> None:
        self.parent_view = parent_view
        self.is_next = is_next
        
        if is_next:
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="Next ▶️",
                disabled=parent_view.page >= parent_view.max_pages - 1,
                custom_id="next_page",
                row=1
            )
        else:
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="◀️ Previous",
                disabled=parent_view.page <= 0,
                custom_id="previous_page",
                row=1
            )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        if self.is_next:
            self.parent_view.page = min(self.parent_view.max_pages - 1, self.parent_view.page + 1)
        else:
            self.parent_view.page = max(0, self.parent_view.page - 1)
            
        self.parent_view.update_buttons()
        self.parent_view.update_dropdown()
        await interaction.response.edit_message(embed=self.parent_view.create_embed(), view=self.parent_view)

class SearchButton(discord.ui.Button):
    def __init__(self, parent_view: 'ModelSelectView') -> None:
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="🔍 Search Models",
            custom_id="search_models"
        )
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction) -> None:
        search_modal = SearchModal()
        
        async def on_submit(modal_interaction: discord.Interaction) -> None:
            search_term = search_modal.search_input.value.strip().lower()
            
            filtered_models = self.parent_view.all_models
            if search_term:
                filtered_models = [model for model in self.parent_view.all_models if search_term in model.get('id', '').lower()]
            
            new_view = ModelSelectView(
                self.parent_view.bot, 
                self.parent_view.all_models,
                filtered_models,
                search_term,
                0,
                self.parent_view.original_interaction
            )
            
            await modal_interaction.response.edit_message(embed=new_view.create_embed(), view=new_view)
            
        search_modal.on_submit = on_submit
        await interaction.response.send_modal(search_modal)

class ModelSelectView(discord.ui.View):
    def __init__(
        self, 
        bot: commands.Bot, 
        all_models: List[Dict[str, Any]], 
        filtered_models: Optional[List[Dict[str, Any]]] = None, 
        search_term: str = "", 
        page: int = 0, 
        interaction: Optional[discord.Interaction] = None, 
        timeout: int = 180
    ) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.all_models = all_models
        self.filtered_models = filtered_models or all_models
        self.search_term = search_term
        self.page = page
        self.models_per_page = 25
        self.max_pages = math.ceil(len(self.filtered_models) / self.models_per_page)
        self.original_interaction = interaction
        
        self.add_item(SearchButton(self))
        self.update_buttons()
        self.update_dropdown()
    
    def update_buttons(self) -> None:
        for item in list(self.children):
            if isinstance(item, NavigationButton):
                self.remove_item(item)
        
        self.add_item(NavigationButton(self, is_next=False))
        self.add_item(NavigationButton(self, is_next=True))
    
    def update_dropdown(self) -> None:
        for item in list(self.children):
            if isinstance(item, ModelSelectDropdown):
                self.remove_item(item)
        
        if not self.filtered_models:
            self.add_item(ModelSelectDropdown(self, [], is_empty=True))
            return
        
        start_idx = self.page * self.models_per_page
        end_idx = min(start_idx + self.models_per_page, len(self.filtered_models))
        
        options: List[discord.SelectOption] = []
        for i in range(start_idx, end_idx):
            model = self.filtered_models[i]
            model_id = model.get('id', 'unknown')
            is_default = model_id == self.bot.chat_model
            
            label = f"{model_id}"
            if len(label) > 100:
                label = label[:97] + "..."
                
            options.append(
                discord.SelectOption(
                    label=label,
                    value=model_id,
                    default=is_default
                )
            )
        
        self.add_item(ModelSelectDropdown(self, options))
    
    def create_embed(self) -> discord.Embed:
        title = f"Models matching '{self.search_term}'" if self.search_term else "Available Models"
            
        embed = discord.Embed(
            title=title,
            description=f"Page {self.page + 1}/{max(1, self.max_pages)} • {len(self.filtered_models)} models available",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Current Model",
            value=f"`{self.bot.chat_model}`",
            inline=False
        )
        
        if not self.search_term:
            embed.add_field(
                name="Search",
                value="Click the 🔍 button to search for specific models",
                inline=False
            )
        elif len(self.filtered_models) == 0:
            embed.add_field(
                name="No Results",
                value="No models found matching your search. Try a different search term.",
                inline=False
            )
        
        return embed
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        
        if self.original_interaction:
            try:
                embed = discord.Embed(
                    title="Model Selection Timed Out",
                    description="This selection has expired. Please run the command again to select a model.",
                    color=discord.Color.red()
                )
                await self.original_interaction.edit_original_response(embed=embed, view=self)
            except Exception:
                pass

class ModelAPIClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
    
    async def fetch_available_models(self) -> List[Dict[str, Any]]:
        if not self.base_url or not self.api_key:
            return []
        
        try:
            url = f"{self.base_url}/models"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "data" in data and isinstance(data["data"], list):
                            return [model for model in data["data"] if self._supports_chat_completions(model)]
                        
                        return []
                    else:
                        error_text = await response.text()
                        print(f"Error fetching models: {error_text}")
                        return []
        except Exception as e:
            print(f"Exception fetching models: {e}")
            return []
    
    def _supports_chat_completions(self, model: Dict[str, Any]) -> bool:
        endpoints = model.get("endpoints", model.get("endpoint", []))
        return "/v1/chat/completions" in endpoints or "chat.completions" in endpoints

class ModelCommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @app_commands.command(name="model", description="Select a model for the bot to use")
    @app_commands.describe(search_term="Optional search term to filter available models")
    async def model_command(
        self, 
        interaction: discord.Interaction, 
        search_term: Optional[str] = None
    ) -> None:
        if interaction.user.id != self.bot.config_manager.get("owner_id"):
            await interaction.response.send_message(
                "Only the bot owner can change the model.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        api_client = ModelAPIClient(self.bot.base_url, self.bot.api_key)
        all_models = await api_client.fetch_available_models()
        
        if not all_models:
            await interaction.followup.send(
                "Could not fetch models. Please check your API settings and try again.",
                ephemeral=True
            )
            return
        
        filtered_models = all_models
        if search_term:
            search_term = search_term.lower()
            filtered_models = [model for model in all_models if search_term in model.get('id', '').lower()]
        
        view = ModelSelectView(
            self.bot, 
            all_models, 
            filtered_models, 
            search_term or "", 
            interaction=interaction
        )
        
        await interaction.followup.send(embed=view.create_embed(), view=view, ephemeral=True)

    @app_commands.command(name="model_info", description="Show information about the current model")
    async def model_info_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Current Model",
            description=f"The bot is currently using `{self.bot.chat_model}`",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="API Endpoint",
            value=f"`{self.bot.base_url}`",
            inline=False
        )
        
        embed.add_field(
            name="Change Model",
            value="Use `/model` to select a different model (bot owner only)",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModelCommandsCog(bot))