import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json
import logging
import re
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('character_bot')

class CharacterBot(commands.Bot):
    def __init__(self, character_config: Dict, *args, **kwargs):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, *args, **kwargs)
        
        # Character configuration
        self.character_config = character_config
        self.owner_id = character_config.get("owner_id")
        self.character_name = character_config.get("character_name", "Assistant")
        self.ai_api_key = character_config.get("ai_api_key", "")
        self.ai_provider = character_config.get("ai_provider", "openai")
        
        # Conversation settings
        self.system_prompt = character_config.get("system_prompt", "")
        self.character_description = character_config.get("character_description", "")
        self.character_personality = character_config.get("character_personality", "")
        self.character_scenario = character_config.get("character_scenario", "")
        self.conversation_history = []
        self.max_history_length = character_config.get("max_history_length", 10)
        
        # Response settings
        self.add_character_name = character_config.get("add_character_name", True)
        self.always_reply_mentions = character_config.get("always_reply_mentions", True)
        self.reply_to_name = character_config.get("reply_to_name", True)
        
    async def setup_hook(self):
        # Register slash commands
        self.tree.add_command(app_commands.Command(
            name="character_info",
            description="Show information about this character",
            callback=self.character_info_command
        ))
        
        # Owner-only commands
        for guild_id in self.character_config.get("allowed_guilds", []):
            guild = discord.Object(id=guild_id)
            self.tree.add_command(app_commands.Command(
                name="edit_prompt",
                description="Edit the character's system prompt",
                callback=self.edit_prompt_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="edit_description",
                description="Edit the character's description",
                callback=self.edit_description_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="edit_personality",
                description="Edit the character's personality",
                callback=self.edit_personality_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="edit_scenario",
                description="Edit the character's scenario",
                callback=self.edit_scenario_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="toggle_setting",
                description="Toggle a character setting",
                callback=self.toggle_setting_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="save_config",
                description="Save the current configuration",
                callback=self.save_config_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="clear_history",
                description="Clear conversation history",
                callback=self.clear_history_command
            ), guild=guild)
    
    async def character_info_command(self, interaction: discord.Interaction):
        """Public command to show character information"""
        embed = discord.Embed(title=f"{self.character_name} Info", color=0x3498db)
        embed.add_field(name="Description", value=self.character_description[:1024] or "No description set", inline=False)
        embed.add_field(name="Personality", value=self.character_personality[:1024] or "No personality set", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    async def edit_prompt_command(self, interaction: discord.Interaction):
        """Edit the character's system prompt"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
            
        # Create modal for editing
        modal = PromptEditModal(title="Edit System Prompt", current_text=self.system_prompt)
        
        async def on_submit(modal_interaction):
            self.system_prompt = modal.prompt_input.value
            await modal_interaction.response.send_message(f"System prompt updated!", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    # Similar edit commands for description, personality, and scenario...
    
    async def toggle_setting_command(self, interaction: discord.Interaction):
        """Toggle a character setting"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
        
        # Create a view with toggleable settings
        view = SettingsView(self)
        await interaction.response.send_message("Character Settings:", view=view, ephemeral=True)
    
    async def save_config_command(self, interaction: discord.Interaction):
        """Save the current configuration"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
        
        # Update config dictionary
        self.character_config.update({
            "system_prompt": self.system_prompt,
            "character_description": self.character_description,
            "character_personality": self.character_personality,
            "character_scenario": self.character_scenario,
            "add_character_name": self.add_character_name,
            "reply_to_name": self.reply_to_name,
            "always_reply_mentions": self.always_reply_mentions,
            "max_history_length": self.max_history_length
        })
        
        # Save to database (placeholder - implement with your DB)
        # save_to_database(self.character_config)
        
        await interaction.response.send_message("Configuration saved!", ephemeral=True)
    
    async def clear_history_command(self, interaction: discord.Interaction):
        """Clear conversation history"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
        
        self.conversation_history = []
        await interaction.response.send_message("Conversation history cleared!", ephemeral=True)
    
    async def on_ready(self):
        logger.info(f'Logged in as {self.user.name} ({self.user.id})')
        
    async def on_message(self, message: discord.Message):
        """Process incoming messages and respond if appropriate"""
        # Ignore own messages
        if message.author == self.user:
            return
            
        # Process commands with prefix
        await self.process_commands(message)
        
        # Check if we should respond
        should_respond = False
        
        # Respond to direct mentions
        if self.user.mentioned_in(message) and self.always_reply_mentions:
            should_respond = True
            
        # Respond when name is called
        if self.reply_to_name and self.character_name.lower() in message.content.lower():
            should_respond = True
            
        if should_respond:
            # Remove mentions from the message
            clean_content = re.sub(r'<@!?(\d+)>', '', message.content).strip()
            
            # Add to conversation history
            self.conversation_history.append({
                "role": "user",
                "name": message.author.display_name,
                "content": clean_content
            })
            
            # Trim history if too long
            if len(self.conversation_history) > self.max_history_length:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
            
            # Generate AI response
            response = await self.generate_response(message.author.display_name, clean_content)
            
            # Add response to history
            self.conversation_history.append({
                "role": "assistant",
                "name": self.character_name,
                "content": response
            })
            
            # Format response with name if enabled
            formatted_response = f"**{self.character_name}**: {response}" if self.add_character_name else response
            
            # Send the response
            await message.reply(formatted_response)
    
    async def generate_response(self, user_name: str, user_message: str) -> str:
        """Generate a response using the configured AI provider"""
        # Construct the full prompt
        full_prompt = self._build_prompt(user_name, user_message)
        
        # This would be replaced with actual API call to your AI provider
        # Placeholder for demonstration
        if self.ai_provider == "openai":
            return await self._call_openai(full_prompt)
        elif self.ai_provider == "anthropic":
            return await self._call_anthropic(full_prompt)
        else:
            # Default mock response for testing
            return f"This is a placeholder response to: {user_message}"
    
    def _build_prompt(self, user_name: str, user_message: str) -> Dict:
        """Build the full prompt for the AI model"""
        messages = []
        
        # System prompt construction
        system_content = f"""**System Directive**
You're {self.character_name}, a character with the following traits:

Description: {self.character_description}
Personality: {self.character_personality}
Scenario: {self.character_scenario}

{self.system_prompt}
"""
        messages.append({"role": "system", "content": system_content})
        
        # Add conversation history
        for entry in self.conversation_history:
            messages.append({"role": entry["role"], "content": entry["content"]})
        
        # Add current message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    async def _call_openai(self, messages: List[Dict]) -> str:
        """Call OpenAI API"""
        # This would be implemented with actual API calls
        # Placeholder for demonstration
        return "This is a placeholder OpenAI response."
    
    async def _call_anthropic(self, messages: List[Dict]) -> str:
        """Call Anthropic API"""
        # This would be implemented with actual API calls
        # Placeholder for demonstration
        return "This is a placeholder Anthropic response."


class PromptEditModal(discord.ui.Modal):
    """Modal for editing text fields"""
    def __init__(self, title: str, current_text: str):
        super().__init__(title=title)
        self.prompt_input = discord.ui.TextInput(
            label="Enter new text:",
            style=discord.TextStyle.paragraph,
            default=current_text,
            max_length=2000
        )
        self.add_item(self.prompt_input)


class SettingsView(discord.ui.View):
    """View for toggling character settings"""
    def __init__(self, bot: CharacterBot):
        super().__init__()
        self.bot = bot
        
    @discord.ui.button(label="Toggle Name in Responses", style=discord.ButtonStyle.secondary)
    async def toggle_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.add_character_name = not self.bot.add_character_name
        await interaction.response.send_message(
            f"Character name in responses: {'Enabled' if self.bot.add_character_name else 'Disabled'}", 
            ephemeral=True
        )
    
    @discord.ui.button(label="Toggle Reply to Name", style=discord.ButtonStyle.secondary)
    async def toggle_reply_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.reply_to_name = not self.bot.reply_to_name
        await interaction.response.send_message(
            f"Reply when name is called: {'Enabled' if self.bot.reply_to_name else 'Disabled'}", 
            ephemeral=True
        )
    
    @discord.ui.button(label="Toggle Reply to Mentions", style=discord.ButtonStyle.secondary)
    async def toggle_mentions(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.always_reply_mentions = not self.bot.always_reply_mentions
        await interaction.response.send_message(
            f"Reply to @mentions: {'Enabled' if self.bot.always_reply_mentions else 'Disabled'}", 
            ephemeral=True
        )


# Example of how to run the bot
def run_bot(config_path: str):
    """Run a character bot with the specified configuration"""
    # Load configuration from file
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Create and run the bot
    bot = CharacterBot(config)
    bot.run(config.get("bot_token"))


# Example configuration structure
example_config = {
    "bot_token": "YOUR_BOT_TOKEN_HERE",
    "owner_id": 123456789012345678,
    "character_name": "Luna",
    "allowed_guilds": [123456789012345678],
    "ai_provider": "openai",
    "ai_api_key": "YOUR_API_KEY_HERE",
    "system_prompt": "You're a helpful assistant named Luna.",
    "character_description": "Luna is a friendly AI assistant who loves helping people.",
    "character_personality": "Cheerful, kind, and always eager to help.",
    "character_scenario": "Luna is in a Discord server answering questions for users.",
    "add_character_name": True,
    "reply_to_name": True,
    "always_reply_mentions": True,
    "max_history_length": 10
}

# This would be called from the bot manager service
if __name__ == "__main__":
    # For testing, you'd have a config file for a single bot
    run_bot("config.json")