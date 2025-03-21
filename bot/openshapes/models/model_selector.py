import discord
import logging
from typing import List, Optional, Protocol, Any, TypeVar, Coroutine, Union
from dataclasses import dataclass
from discord import ui

logger = logging.getLogger("openshape")

T = TypeVar('T')

@dataclass
class ModelInfo:
    id: str
    name: str
    description: str = ""

class ModelRepository(Protocol):
    async def fetch_models(self) -> List[ModelInfo]:
        pass
    
    def get_model_by_id(self, model_id: str) -> Optional[ModelInfo]:
        pass

class ModelSelectionListener(Protocol):
    async def on_model_selected(self, model: ModelInfo) -> None:
        pass

class ModelPermissionChecker(Protocol):
    async def can_select_models(self, interaction: discord.Interaction) -> bool:
        pass

class OpenAIModelRepository:
    def __init__(self, ai_client: Any):
        self.ai_client = ai_client
        self._models: List[ModelInfo] = []
        
    async def fetch_models(self) -> List[ModelInfo]:
        if not self.ai_client:
            logger.warning("No AI client configured, can't fetch models")
            return []
            
        try:
            response = await self.ai_client.models.list()
            self._models = []
            
            for model in response.data:
                if "chat" not in model.id.lower() and "instruct" not in model.id.lower():
                    continue
                    
                self._models.append(ModelInfo(
                    id=model.id,
                    name=model.id.split("/")[-1] if "/" in model.id else model.id,
                    description=getattr(model, "description", "")
                ))
                
            return self._models
        except Exception as e:
            logger.error(f"Error fetching models: {e}")
            return []
            
    def get_model_by_id(self, model_id: str) -> Optional[ModelInfo]:
        return next((m for m in self._models if m.id == model_id), None)

class BotModelSelectionListener:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def on_model_selected(self, model: ModelInfo) -> None:
        self.bot.chat_model = model.id
        self.bot.api_settings["chat_model"] = model.id
        self.bot.config_manager_obj.save_config()

class BotOwnerPermissionChecker:
    def __init__(self, owner_id: int):
        self.owner_id = owner_id
        
    async def can_select_models(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can change the AI model", ephemeral=True
            )
            return False
        return True

class ModelSelectionView(ui.View):
    def __init__(
        self,
        models: List[ModelInfo],
        repository: ModelRepository,
        selection_listener: ModelSelectionListener,
        timeout: int = 60
    ):
        super().__init__(timeout=timeout)
        self.models = models
        self.repository = repository
        self.selection_listener = selection_listener
        
        self._build_buttons()
        
    def _build_buttons(self) -> None:
        for model in self.models[:25]:
            button = ui.Button(
                label=model.name,
                style=discord.ButtonStyle.secondary,
                custom_id=model.id
            )
            button.callback = self._create_callback(model.id)
            self.add_item(button)
            
    def _create_callback(self, model_id: str) -> Union[None, Coroutine[Any, Any, None]]:
        async def callback(interaction: discord.Interaction) -> None:
            await self._handle_model_selection(interaction, model_id)
        return callback
    
    async def _handle_model_selection(self, interaction: discord.Interaction, model_id: str) -> None:
        selected_model = self.repository.get_model_by_id(model_id)
        
        if not selected_model:
            await interaction.response.send_message("Error: Model not found", ephemeral=True)
            return

        await self.selection_listener.on_model_selected(selected_model)
        
        await interaction.response.send_message(
            f"AI model switched to: **{selected_model.name}**", ephemeral=True
        )

        embed = discord.Embed(
            title="Model Selection",
            description=f"Current model: **{selected_model.name}**",
            color=discord.Color.green()
        )
        await interaction.message.edit(embed=embed, view=None)

class ModelSelectionController:
    def __init__(
        self,
        repository: ModelRepository,
        listener: ModelSelectionListener,
        permission_checker: ModelPermissionChecker
    ):
        self.repository = repository
        self.listener = listener
        self.permission_checker = permission_checker
        
    async def display_model_selection(self, interaction: discord.Interaction, current_model_id: str) -> None:
        if not await self.permission_checker.can_select_models(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        models = await self.repository.fetch_models()
        
        if not models:
            await interaction.followup.send(
                "No models found or couldn't fetch models from API.", ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="Select AI Model",
            description=f"Current model: **{current_model_id}**\nChoose a model to use:",
            color=discord.Color.blue()
        )
        
        view = ModelSelectionView(models, self.repository, self.listener)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

async def model_command(bot, interaction: discord.Interaction) -> None:
    if not bot.ai_client:
        await interaction.response.send_message(
            "AI client not configured. Set API settings first.", ephemeral=True
        )
        return
    
    repository = OpenAIModelRepository(bot.ai_client)
    listener = BotModelSelectionListener(bot)
    permission_checker = BotOwnerPermissionChecker(bot.owner_id)
    
    controller = ModelSelectionController(repository, listener, permission_checker)
    await controller.display_model_selection(interaction, bot.chat_model)
