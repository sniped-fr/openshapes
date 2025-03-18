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
            "character_name": self.character_name,
            "system_prompt": self.system_prompt,
            "character_description": self.character_description,
            "character_personality": self.character_personality,
            "character_scenario": self.character_scenario,
            "add_character_name": self.add_character_name,
            "reply_to_name": self.reply_to_name,
            "always_reply_mentions": self.always_reply_mentions,
            "max_history_length": self.max_history_length,
            "long_term_memory": self.long_term_memory,
            "lorebook_entries": self.lorebook_entries,
            "knowledge_base": self.knowledge_base,
            "blacklisted_users": self.blacklisted_users,
            "blacklisted_roles": self.blacklisted_roles,
            "voice_enabled": self.voice_enabled,
            "voice_provider": self.voice_provider,
            "voice_id": self.voice_id
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
    
    async def memory_command(self, interaction: discord.Interaction):
        """Slash command to manage memory"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
        
        # Create a view with memory management options
        view = MemoryManagementView(self)
        
        memory_display = "**Long-term Memory:**\n"
        if not self.long_term_memory:
            memory_display += "No memories stored yet."
        else:
            for topic, details in self.long_term_memory.items():
                memory_display += f"- **{topic}**: {details}\n"
        
        await interaction.response.send_message(memory_display, view=view, ephemeral=True)
        
    async def lorebook_command(self, interaction: discord.Interaction):
        """Slash command to manage lorebook entries"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
            
        # Create a modal for adding lorebook entries
        modal = LorebookEntryModal(title="Add Lorebook Entry")
        
        async def on_submit(modal_interaction):
            new_entry = {
                "keyword": modal.keyword_input.value,
                "content": modal.content_input.value
            }
            self.lorebook_entries.append(new_entry)
            await modal_interaction.response.send_message(f"Added lorebook entry for keyword: {new_entry['keyword']}", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def knowledge_command(self, interaction: discord.Interaction):
        """Slash command to manage knowledge base"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
            
        # Create a modal for editing knowledge base
        modal = KnowledgeBaseModal(title="Edit Knowledge Base", current_text=self.knowledge_base)
        
        async def on_submit(modal_interaction):
            self.knowledge_base = modal.knowledge_input.value
            await modal_interaction.response.send_message("Knowledge base updated!", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def voice_command(self, interaction: discord.Interaction):
        """Slash command to configure voice settings"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
        
        # Get the voice channels in the server
        voice_channels = [channel for channel in interaction.guild.channels if isinstance(channel, discord.VoiceChannel)]
        
        # Create a select menu with voice channels
        select = discord.ui.Select(
            placeholder="Select a voice channel to join",
            options=[discord.SelectOption(label=channel.name, value=str(channel.id)) for channel in voice_channels]
        )
        
        async def select_callback(select_interaction):
            channel_id = int(select.values[0])
            channel = interaction.guild.get_channel(channel_id)
            
            # Join the voice channel
            try:
                if hasattr(self, 'voice_client') and self.voice_client is not None:
                    await self.voice_client.disconnect()
                    
                self.voice_client = await channel.connect()
                self.voice_enabled = True
                await select_interaction.response.send_message(f"Connected to voice channel: {channel.name}", ephemeral=True)
            except Exception as e:
                await select_interaction.response.send_message(f"Error connecting to voice channel: {e}", ephemeral=True)
        
        select.callback = select_callback
        
        # Create a button to disconnect from voice
        disconnect_button = discord.ui.Button(label="Disconnect from Voice", style=discord.ButtonStyle.danger)
        
        async def disconnect_callback(button_interaction):
            if hasattr(self, 'voice_client') and self.voice_client is not None:
                await self.voice_client.disconnect()
                self.voice_client = None
                self.voice_enabled = False
                await button_interaction.response.send_message("Disconnected from voice channel", ephemeral=True)
            else:
                await button_interaction.response.send_message("Not connected to a voice channel", ephemeral=True)
        
        disconnect_button.callback = disconnect_callback
        
        # Create buttons for voice model selection
        tts1_button = discord.ui.Button(label="TTS-1 (Alloy)", style=discord.ButtonStyle.primary)
        
        async def tts1_callback(button_interaction):
            self.voice_provider = "tts-1"
            self.voice_id = "alloy"
            await button_interaction.response.send_message("Voice set to TTS-1 (Alloy)", ephemeral=True)
        
        tts1_button.callback = tts1_callback
        
        # Create the view and add the components
        view = discord.ui.View()
        view.add_item(select)
        view.add_item(disconnect_button)
        view.add_item(tts1_button)
        
        await interaction.response.send_message("Voice Channel Settings:", view=view, ephemeral=True)
    
    async def blacklist_command(self, interaction: discord.Interaction):
        """Slash command to manage blacklisted users/roles"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
        
        # Create a modal for selecting a user or role
        class BlacklistModal(discord.ui.Modal):
            def __init__(self):
                super().__init__(title="Add to Blacklist")
                self.user_id_input = discord.ui.TextInput(
                    label="User ID (leave blank for role)",
                    placeholder="Enter user ID to blacklist",
                    required=False
                )
                self.role_id_input = discord.ui.TextInput(
                    label="Role ID (leave blank for user)",
                    placeholder="Enter role ID to blacklist",
                    required=False
                )
                self.add_item(self.user_id_input)
                self.add_item(self.role_id_input)
        
        modal = BlacklistModal()
        
        async def on_submit(modal_interaction):
            try:
                if modal.user_id_input.value:
                    user_id = int(modal.user_id_input.value)
                    if user_id not in self.blacklisted_users:
                        self.blacklisted_users.append(user_id)
                        await modal_interaction.response.send_message(f"Added user ID {user_id} to blacklist", ephemeral=True)
                    else:
                        await modal_interaction.response.send_message(f"User ID {user_id} is already blacklisted", ephemeral=True)
                elif modal.role_id_input.value:
                    role_id = int(modal.role_id_input.value)
                    if role_id not in self.blacklisted_roles:
                        self.blacklisted_roles.append(role_id)
                        await modal_interaction.response.send_message(f"Added role ID {role_id} to blacklist", ephemeral=True)
                    else:
                        await modal_interaction.response.send_message(f"Role ID {role_id} is already blacklisted", ephemeral=True)
                else:
                    await modal_interaction.response.send_message("Please enter a user ID or role ID", ephemeral=True)
            except ValueError:
                await modal_interaction.response.send_message("Invalid ID format. Please enter a valid number.", ephemeral=True)
                
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    async def import_command(self, interaction: discord.Interaction):
        """Slash command to import a character card"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
        
        # Check if there's an attachment
        if not interaction.message or not interaction.message.attachments:
            await interaction.response.send_message("Please upload a character card file with this command", ephemeral=True)
            return
        
        # Process the first attachment
        attachment = interaction.message.attachments[0]
        card_data = await self._parse_character_card(attachment)
        
        if "error" in card_data:
            await interaction.response.send_message(f"Error importing character card: {card_data['error']}", ephemeral=True)
            return
        
        # Update character data
        if "name" in card_data:
            self.character_name = card_data["name"]
        if "description" in card_data:
            self.character_description = card_data["description"]
        if "personality" in card_data:
            self.character_personality = card_data["personality"]
        if "scenario" in card_data:
            self.character_scenario = card_data["scenario"]
        if "system_prompt" in card_data:
            self.system_prompt = card_data["system_prompt"]
        if "avatar_url" in card_data:
            self.avatar_url = card_data["avatar_url"]
        if "lorebook_entries" in card_data:
            self.lorebook_entries = card_data["lorebook_entries"]
        if "knowledge_base" in card_data:
            self.knowledge_base = card_data["knowledge_base"]
        
        # Save the imported data
        await self.save_config_command(interaction)
        
        await interaction.response.send_message(f"Successfully imported character card for {self.character_name}!", ephemeral=True)    # Public slash commands
    async def activate_command(self, interaction: discord.Interaction):
        """Slash command to activate the bot in a channel"""
        # Check if the user has permission to manage channels
        if not interaction.channel.permissions_for(interaction.user).manage_channels:
            await interaction.response.send_message("You need 'Manage Channels' permission to use this command", ephemeral=True)
            return
            
        self.activated_channels.add(interaction.channel.id)
        await interaction.response.send_message(f"{self.character_name} will now respond to all messages in this channel.")
    
    async def deactivate_command(self, interaction: discord.Interaction):
        """Slash command to deactivate the bot in a channel"""
        # Check if the user has permission to manage channels
        if not interaction.channel.permissions_for(interaction.user).manage_channels:
            await interaction.response.send_message("You need 'Manage Channels' permission to use this command", ephemeral=True)
            return
            
        if interaction.channel.id in self.activated_channels:
            self.activated_channels.remove(interaction.channel.id)
        await interaction.response.send_message(f"{self.character_name} will now only respond when mentioned or called by name.")
    
    async def purge_command(self, interaction: discord.Interaction):
        """Slash command to delete recent bot messages"""
        # Check if the user has permission to manage messages
        if not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.response.send_message("You need 'Manage Messages' permission to use this command", ephemeral=True)
            return
            
        # Acknowledge the command
        await interaction.response.send_message("Deleting recent messages...", ephemeral=True)
        
        # Get recent messages in the channel
        deleted_count = 0
        async for message in interaction.channel.history(limit=50):
            if message.author == self.user:
                await message.delete()
                deleted_count += 1
                # Respect rate limits
                if deleted_count % 5 == 0:
                    await asyncio.sleep(5)
        
        # Send confirmation
        await interaction.followup.send(f"Deleted {deleted_count} messages from {self.character_name}.", ephemeral=True)
    
    async def whack_command(self, interaction: discord.Interaction):
        """Slash command to clear the bot's short-term memory buffer"""
        self.conversation_history = []
        await interaction.response.send_message(f"Cleared {self.character_name}'s memory buffer!")
    
    async def reroll_command(self, interaction: discord.Interaction):
        """Slash command to regenerate the last response"""
        if not self.last_prompt:
            await interaction.response.send_message("No recent message to reroll.", ephemeral=True)
            return
            
        # Acknowledge the command
        await interaction.response.send_message("Generating a new response...", ephemeral=True)
        
        # Increment reroll count
        self.reroll_count += 1
        
        # Remove the last assistant message from history if it exists
        if self.conversation_history and self.conversation_history[-1]["role"] == "assistant":
            self.conversation_history.pop()
        
        # Generate a new response
        response = await self.generate_response(self.last_prompt)
        
        # Add response to history
        self.conversation_history.append({
            "role": "assistant",
            "name": self.character_name,
            "content": response
        })
        
        # Format response with name if enabled
        formatted_response = f"**{self.character_name}**: {response}" if self.add_character_name else response
        
        # Send the new response
        await interaction.followup.send(formatted_response)
    
    async def export_command(self, interaction: discord.Interaction):
        """Slash command to export the character"""
        card_data = self._generate_character_card()
        
        # Create JSON file
        json_file = discord.File(
            io.BytesIO(json.dumps(card_data, indent=2).encode()),
            filename=f"{self.character_name.replace(' ', '_')}.json"
        )
        
        await interaction.response.send_message(f"Character card for {self.character_name}:", file=json_file)
    
    # Character info command (public)
    async def character_info_command(self, interaction: discord.Interaction):
        """Public command to show character information"""
        embed = discord.Embed(title=f"{self.character_name} Info", color=0x3498db)
        embed.add_field(name="Description", value=self.character_description[:1024] or "No description set", inline=False)
        embed.add_field(name="Personality", value=self.character_personality[:1024] or "No personality set", inline=False)
        
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        await interaction.response.send_message(embed=embed)
    
    # Owner-only commands
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
    
    async def edit_description_command(self, interaction: discord.Interaction):
        """Edit the character's description"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
            
        # Create modal for editing
        modal = PromptEditModal(title="Edit Character Description", current_text=self.character_description)
        
        async def on_submit(modal_interaction):
            self.character_description = modal.prompt_input.value
            await modal_interaction.response.send_message(f"Character description updated!", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    async def edit_personality_command(self, interaction: discord.Interaction):
        """Edit the character's personality"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
            
        # Create modal for editing
        modal = PromptEditModal(title="Edit Character Personality", current_text=self.character_personality)
        
        async def on_submit(modal_interaction):
            self.character_personality = modal.prompt_input.value
            await modal_interaction.response.send_message(f"Character personality updated!", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
    
    async def edit_scenario_command(self, interaction: discord.Interaction):
        """Edit the character's scenario"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
            
        # Create modal for editing
        modal = PromptEditModal(title="Edit Character Scenario", current_text=self.character_scenario)
        
        async def on_submit(modal_interaction):
            self.character_scenario = modal.prompt_input.value
            await modal_interaction.response.send_message(f"Character scenario updated!", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)    async def generate_response(self, prompt: List[Dict]) -> str:
        """Generate a response using the configured AI provider"""
        try:
            # Call the API based on provider
            if self.ai_provider == "openai" or self.ai_provider == "zukijourney":
                # Format messages for OpenAI-compatible APIs
                completion = self.ai_client.chat.completions.create(
                    model=self.ai_model,
                    messages=prompt,
                    stream=False
                )
                return completion.choices[0].message.content
            else:
                # Default mock response for testing
                return f"This is a placeholder response."
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"I'm sorry, I encountered an error trying to respond. Please try again later."
    
    def _build_prompt(self, user_name: str, user_message: str, relevant_lore: List[str] = None) -> List[Dict]:
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
        
        # Add knowledge base if available
        if self.knowledge_base:
            system_content += f"\n\n**Knowledge Base:**\n{self.knowledge_base}"
        
        # Add memory if available
        if self.long_term_memory:
            memory_content = "\n\n**What you remember about this conversation and the users:**\n"
            for topic, details in self.long_term_memory.items():
                memory_content += f"- {topic}: {details}\n"
            system_content += memory_content
        
        # Add relevant lorebook entries if available
        if relevant_lore and len(relevant_lore) > 0:
            lore_content = "\n\n**Relevant information for this response:**\n"
            for lore in relevant_lore:
                lore_content += f"- {lore}\n"
            system_content += lore_content
        
        messages.append({"role": "system", "content": system_content})
        
        # Add conversation history
        for entry in self.conversation_history:
            messages.append({"role": entry["role"], "content": entry["content"]})
        
        # Add current message if not in history already
        if self.conversation_history and self.conversation_history[-1]["role"] != "user":
            messages.append({"role": "user", "content": user_message})
        
        return messages
    
    async def _generate_memory(self):
        """Generate or update long-term memory based on conversation history"""
        if not self.conversation_history:
            return
        
        # Build a prompt for the AI to generate/update memory
        memory_prompt = [
            {"role": "system", "content": "Your task is to extract and summarize key information from the conversation to create long-term memory for the character. Focus on important facts, relationships, preferences, and events that would be useful for the character to remember in future conversations. Format your response as JSON."},
            {"role": "user", "content": f"Based on the following conversation history, update the character's long-term memory by identifying key information. Current memory: {json.dumps(self.long_term_memory)}\n\nConversation:\n" + "\n".join([f"{msg['name']}: {msg['content']}" for msg in self.conversation_history])}
        ]
        
        try:
            # Call the AI to generate memory
            memory_response = await self.generate_response(memory_prompt)
            
            # Parse and update the memory
            try:
                # Try to extract JSON from the response (it might be surrounded by markdown code blocks)
                json_match = re.search(r'```(?:json)?(.*?)```', memory_response, re.DOTALL)
                if json_match:
                    memory_json = json_match.group(1).strip()
                else:
                    memory_json = memory_response.strip()
                
                new_memories = json.loads(memory_json)
                if isinstance(new_memories, dict):
                    # Update the existing memory with new information
                    self.long_term_memory.update(new_memories)
            except json.JSONDecodeError:
                # If it's not valid JSON, try to extract key points manually
                lines = memory_response.split('\n')
                for line in lines:
                    if ':' in line:
                        topic, details = line.split(':', 1)
                        self.long_term_memory[topic.strip()] = details.strip()
        
        except Exception as e:
            logger.error(f"Error generating memory: {e}")
    
    async def _speak_response(self, text: str):
        """Generate and play text-to-speech audio for the response"""
        if not self.voice_enabled or not hasattr(self, 'voice_client') or not self.voice_client:
            return
            
        try:
            # Generate speech using OpenAI API
            response = self.ai_client.audio.speech.create(
                model=self.voice_provider,
                voice=self.voice_id,
                input=text
            )
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_file.close()
            
            # Stream to file
            response.stream_to_file(temp_file.name)
            
            # Play the audio
            audio_source = discord.FFmpegPCMAudio(temp_file.name)
            
            if self.voice_client.is_playing():
                self.voice_client.stop()
                
            self.voice_client.play(audio_source, after=lambda e: os.remove(temp_file.name) if e is None else print(f'Error playing file: {e}'))
            
        except Exception as e:
            logger.error(f"Error generating speech: {e}")
    
    def _generate_character_card(self) -> Dict:
        """Generate a character card data structure for export"""
        return {
            "name": self.character_name,
            "description": self.character_description,
            "personality": self.character_personality,
            "scenario": self.character_scenario,
            "system_prompt": self.system_prompt,
            "first_message": "",  # Optional first message
            "avatar_url": self.avatar_url,
            "lorebook_entries": self.lorebook_entries,
            "knowledge_base": self.knowledge_base,
            "long_term_memory": self.long_term_memory,
            "created_at": discord.utils.utcnow().isoformat(),
            "creator": f"OpenShapes Bot ID: {self.user.id}"
        }
    
    async def _parse_character_card(self, attachment: discord.Attachment) -> Dict:
        """Parse a character card from an attachment"""
        try:
            # Download the attachment
            content = await attachment.read()
            
            # Check if it's a JSON file
            if attachment.filename.endswith('.json'):
                card_data = json.loads(content.decode('utf-8'))
                return card_data
            
            # Check if it's an image (might have embedded JSON)
            elif attachment.content_type.startswith('image/'):
                # For images, you'd need to extract any embedded data
                # This is a simplified version that assumes no embedded data
                return {"error": "Image-based character cards not fully supported yet"}
            
            else:
                return {"error": "Unsupported file format"}
                
        except Exception as e:
            logger.error(f"Error parsing character card: {e}")
            return {"error": str(e)}import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json
import logging
import re
import os
import base64
import tempfile
from typing import Dict, List, Optional, Union, Any
from openai import OpenAI
import aiohttp
import io
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('character_bot')

class CharacterBot(commands.Bot):
    def __init__(self, character_config: Dict, *args, **kwargs):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        intents.reactions = True
        super().__init__(command_prefix="!", intents=intents, *args, **kwargs)
        
        # Character configuration
        self.character_config = character_config
        self.owner_id = character_config.get("owner_id")
        self.character_name = character_config.get("character_name", "Assistant")
        
        # AI API settings
        self.ai_api_key = character_config.get("ai_api_key", "")
        self.ai_provider = character_config.get("ai_provider", "openai")
        self.ai_model = character_config.get("ai_model", "gpt-3.5-turbo")
        self.ai_base_url = character_config.get("ai_base_url", "https://api.openai.com/v1")
        
        # OpenAI client
        self.ai_client = OpenAI(
            api_key=self.ai_api_key,
            base_url=self.ai_base_url,
            max_retries=1,
            timeout=60
        )
        
        # Conversation settings
        self.system_prompt = character_config.get("system_prompt", "")
        self.character_description = character_config.get("character_description", "")
        self.character_personality = character_config.get("character_personality", "")
        self.character_scenario = character_config.get("character_scenario", "")
        self.conversation_history = []
        self.max_history_length = character_config.get("max_history_length", 10)
        
        # Memory system
        self.long_term_memory = character_config.get("long_term_memory", {})
        self.auto_memory_generation = character_config.get("auto_memory_generation", True)
        self.memory_generation_interval = character_config.get("memory_generation_interval", 10)  # Generate after every 10 messages
        self.message_count = 0
        
        # Lorebook/Knowledge base
        self.lorebook_entries = character_config.get("lorebook_entries", [])
        self.knowledge_base = character_config.get("knowledge_base", "")
        
        # Response behavior settings
        self.add_character_name = character_config.get("add_character_name", True)
        self.always_reply_mentions = character_config.get("always_reply_mentions", True)
        self.reply_to_name = character_config.get("reply_to_name", True)
        self.is_activated = False  # For /activate and /deactivate commands
        self.activated_channels = set()
        
        # Voice settings
        self.voice_enabled = character_config.get("voice_enabled", False)
        self.voice_provider = character_config.get("voice_provider", "tts-1")
        self.voice_id = character_config.get("voice_id", "alloy")
        self.voice_client = None
        
        # Moderation settings
        self.blacklisted_users = character_config.get("blacklisted_users", [])
        self.blacklisted_roles = character_config.get("blacklisted_roles", [])
        
        # Character card data
        self.avatar_url = character_config.get("avatar_url", "")
        self.card_data = character_config.get("card_data", {})
        
        # Reroll system
        self.last_prompt = None  # Store the last prompt for rerolling
        self.reroll_count = 0  # Track number of rerolls
        
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
        
        # Public commands
        self.tree.add_command(app_commands.Command(
            name="activate",
            description="Activate the bot to respond to all messages in the channel",
            callback=self.activate_command
        ))
        
        self.tree.add_command(app_commands.Command(
            name="deactivate",
            description="Deactivate the bot's automatic responses in the channel",
            callback=self.deactivate_command
        ))
        
        self.tree.add_command(app_commands.Command(
            name="purge",
            description="Delete recent bot messages in this channel",
            callback=self.purge_command
        ))
        
        self.tree.add_command(app_commands.Command(
            name="whack",
            description="Clear the bot's short-term memory buffer",
            callback=self.whack_command
        ))
        
        self.tree.add_command(app_commands.Command(
            name="reroll",
            description="Generate a new response to the last message",
            callback=self.reroll_command
        ))
        
        self.tree.add_command(app_commands.Command(
            name="export",
            description="Export this character as a character card",
            callback=self.export_command
        ))
        
        # Owner-only commands
        for guild_id in self.character_config.get("allowed_guilds", []):
            guild = discord.Object(id=guild_id)
            
            # Character editing commands
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
            
            # Settings commands
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
            
            # Memory and Lorebook commands
            self.tree.add_command(app_commands.Command(
                name="memory",
                description="View or manage the character's memory",
                callback=self.memory_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="lorebook",
                description="Manage lorebook entries",
                callback=self.lorebook_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="knowledge",
                description="View or update the character's knowledge base",
                callback=self.knowledge_command
            ), guild=guild)
            
            # Voice and moderation commands
            self.tree.add_command(app_commands.Command(
                name="voice",
                description="Configure voice settings for the character",
                callback=self.voice_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="blacklist",
                description="Add a user or role to the blacklist",
                callback=self.blacklist_command
            ), guild=guild)
            self.tree.add_command(app_commands.Command(
                name="import",
                description="Import a character from a character card",
                callback=self.import_command
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
        
        # Check if user or role is blacklisted
        if self._is_blacklisted(message.author):
            return
        
        # Check if we should respond
        should_respond = False
        
        # Check if the channel is activated for responding to all messages
        if message.channel.id in self.activated_channels:
            should_respond = True
        
        # Respond to direct mentions
        elif self.user.mentioned_in(message) and self.always_reply_mentions:
            should_respond = True
            
        # Respond when name is called
        elif self.reply_to_name and self.character_name.lower() in message.content.lower():
            should_respond = True
            
        # Check for OOC command prefix (out of character)
        is_ooc = message.content.startswith("//") or message.content.startswith("/ooc")
        if is_ooc and message.author.id == self.owner_id:
            await self._handle_ooc_command(message)
            return
            
        if should_respond:
            # Remove mentions from the message
            clean_content = re.sub(r'<@!?(\d+)>', '', message.content).strip()
            
            # Add to conversation history
            self.conversation_history.append({
                "role": "user",
                "name": message.author.display_name,
                "content": clean_content
            })
            
            # Increment message count for auto-memory generation
            self.message_count += 1
            
            # Check if we should generate memory
            if self.auto_memory_generation and self.message_count >= self.memory_generation_interval:
                await self._generate_memory()
                self.message_count = 0
            
            # Get relevant lorebook entries
            relevant_lore = self._get_relevant_lorebook_entries(clean_content)
            
            # Trim history if too long
            if len(self.conversation_history) > self.max_history_length:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
            
            # Generate AI response
            prompt = self._build_prompt(message.author.display_name, clean_content, relevant_lore)
            self.last_prompt = prompt  # Store for reroll command
            self.reroll_count = 0
            
            response = await self.generate_response(prompt)
            
            # Add response to history
            self.conversation_history.append({
                "role": "assistant",
                "name": self.character_name,
                "content": response
            })
            
            # Format response with name if enabled
            formatted_response = f"**{self.character_name}**: {response}" if self.add_character_name else response
            
            # Check if we're in a voice channel and should use TTS
            if self.voice_enabled and hasattr(self, 'voice_client') and self.voice_client is not None and self.voice_client.is_connected():
                # Generate TTS and play it
                await self._speak_response(response)
            
            # Send the response and add reaction for deletion
            sent_message = await message.reply(formatted_response)
            await sent_message.add_reaction("🗑️")
    
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle reactions to messages"""
        # If the reaction is the trash emoji on the bot's message and from message author or bot owner
        if (reaction.emoji == "🗑️" and reaction.message.author == self.user and 
            (user.id == self.owner_id or user.id == reaction.message.reference.resolved.author.id)):
            await reaction.message.delete()
    
    def _is_blacklisted(self, user: discord.User) -> bool:
        """Check if a user is blacklisted"""
        # Check if user ID is blacklisted
        if user.id in self.blacklisted_users:
            return True
        
        # Check if any of user's roles are blacklisted
        if hasattr(user, 'roles'):  # Only works in guild context
            for role in user.roles:
                if role.id in self.blacklisted_roles:
                    return True
        
        return False
            
    async def _handle_ooc_command(self, message: discord.Message):
        """Handle out-of-character commands from the owner"""
        clean_content = message.content.replace("//", "").replace("/ooc", "").strip()
        parts = clean_content.split(' ', 1)
        command = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        
        if command == "memory":
            if args.lower() == "generate":
                await self._generate_memory()
                await message.reply("Memory generated!", ephemeral=True)
            elif args.lower() == "show":
                memory_display = "**Long-term Memory:**\n"
                for topic, details in self.long_term_memory.items():
                    memory_display += f"- **{topic}**: {details}\n"
                await message.reply(memory_display, ephemeral=True)
        
        elif command == "lore":
            subparts = args.split(' ', 1)
            subcommand = subparts[0].lower() if subparts else ""
            subargs = subparts[1] if len(subparts) > 1 else ""
            
            if subcommand == "add" and subargs:
                try:
                    lore_data = json.loads(subargs)
                    if isinstance(lore_data, dict) and "keyword" in lore_data and "content" in lore_data:
                        self.lorebook_entries.append(lore_data)
                        await message.reply(f"Added lorebook entry for keyword: {lore_data['keyword']}", ephemeral=True)
                    else:
                        await message.reply("Invalid format. Use: //lore add {\"keyword\": \"word\", \"content\": \"details\"}", ephemeral=True)
                except json.JSONDecodeError:
                    await message.reply("Invalid JSON format. Use: //lore add {\"keyword\": \"word\", \"content\": \"details\"}", ephemeral=True)
            elif subcommand == "list":
                lore_display = "**Lorebook Entries:**\n"
                for i, entry in enumerate(self.lorebook_entries):
                    lore_display += f"{i+1}. **{entry['keyword']}**: {entry['content'][:50]}...\n"
                await message.reply(lore_display, ephemeral=True)
        
        elif command == "knowledge":
            if args.lower() == "show":
                knowledge_display = f"**Knowledge Base:**\n{self.knowledge_base[:1500]}..."
                await message.reply(knowledge_display, ephemeral=True)
            else:
                # Set knowledge base
                self.knowledge_base = args
                await message.reply("Knowledge base updated!", ephemeral=True)
        
        elif command == "activate":
            self.activated_channels.add(message.channel.id)
            await message.reply(f"{self.character_name} will now respond to all messages in this channel.", ephemeral=True)
            
        elif command == "deactivate":
            if message.channel.id in self.activated_channels:
                self.activated_channels.remove(message.channel.id)
            await message.reply(f"{self.character_name} will now only respond when mentioned or called by name.", ephemeral=True)
            
        elif command == "whack":
            self.conversation_history = []
            await message.reply("Memory buffer cleared!", ephemeral=True)
            
        elif command == "persona":
            # Show current persona details
            persona_display = f"**{self.character_name} Persona:**\n"
            persona_display += f"**Description:** {self.character_description}\n"
            persona_display += f"**Personality:** {self.character_personality}\n"
            persona_display += f"**Scenario:** {self.character_scenario}\n"
            await message.reply(persona_display, ephemeral=True)
        
        elif command == "export":
            card_data = self._generate_character_card()
            await message.reply(f"Character card for {self.character_name}:", file=discord.File(
                io.BytesIO(json.dumps(card_data, indent=2).encode()),
                filename=f"{self.character_name.replace(' ', '_')}.json"
            ))
            
        elif command == "blacklist":
            if not args:
                await message.reply("Usage: //blacklist add @user or //blacklist remove @user", ephemeral=True)
                return
                
            subparts = args.split(' ', 1)
            subcommand = subparts[0].lower()
            
            if len(subparts) > 1 and message.mentions:
                target_user = message.mentions[0]
                
                if subcommand == "add":
                    if target_user.id not in self.blacklisted_users:
                        self.blacklisted_users.append(target_user.id)
                        await message.reply(f"Added {target_user.display_name} to blacklist.", ephemeral=True)
                elif subcommand == "remove":
                    if target_user.id in self.blacklisted_users:
                        self.blacklisted_users.remove(target_user.id)
                        await message.reply(f"Removed {target_user.display_name} from blacklist.", ephemeral=True)
    
    def _get_relevant_lorebook_entries(self, message_content: str) -> List[str]:
        """Get lorebook entries relevant to the current message"""
        relevant_entries = []
        
        for entry in self.lorebook_entries:
            # Check if keyword is in the message
            if entry["keyword"].lower() in message_content.lower():
                relevant_entries.append(entry["content"])
        
        return relevant_entries
    
    async def _generate_memory(self):
        """Generate or update long-term memory based on conversation history"""
        if not self.conversation_history:
            return
        
        # Build a prompt for the AI to generate/update memory
        memory_prompt = [
            {"role": "system", "content": "Your task is to extract and summarize key information from the conversation to create long-term memory for the character. Focus on important facts, relationships, preferences, and events that would be useful for the character to remember in future conversations."},
            {"role": "user", "content": f"Based on the following conversation history, update the character's long-term memory by identifying key information. Current memory: {json.dumps(self.long_term_memory)}\n\nConversation:\n" + "\n".join([f"{msg['name']}: {msg['content']}" for msg in self.conversation_history])}
        ]
        
        try:
            # Call the AI to generate memory (placeholder - implement with actual AI call)
            memory_response = await self._call_ai_for_memory(memory_prompt)
            
            # Parse and update the memory
            try:
                new_memories = json.loads(memory_response)
                if isinstance(new_memories, dict):
                    # Update the existing memory with new information
                    self.long_term_memory.update(new_memories)
            except json.JSONDecodeError:
                # If it's not valid JSON, try to extract key points manually
                lines = memory_response.split('\n')
                for line in lines:
                    if ':' in line:
                        topic, details = line.split(':', 1)
                        self.long_term_memory[topic.strip()] = details.strip()
        
        except Exception as e:
            logger.error(f"Error generating memory: {e}")
    
    async def _call_ai_for_memory(self, prompt: List[Dict]) -> str:
        """Call AI to generate memory (placeholder implementation)"""
        # This would be implemented with actual AI API calls
        # For demonstration purposes, return a sample response
        return json.dumps({
            "User Preferences": "Likes to discuss technology and science fiction",
            "Recent Topics": "Talked about AI ethics and future applications",
            "Character Relationship": "Friendly and helpful, providing informative responses"
        })
    
    async def _speak_response(self, text: str):
        """Speak the response using text-to-speech (placeholder implementation)"""
        # This would be implemented with a TTS service
        # For example, using a local TTS library or cloud TTS API
        pass
    
    async def generate_response(self, user_name: str, user_message: str, relevant_lore: List[str] = None) -> str:
        """Generate a response using the configured AI provider"""
        # Construct the full prompt
        full_prompt = self._build_prompt(user_name, user_message, relevant_lore)
        
        # This would be replaced with actual API call to your AI provider
        # Placeholder for demonstration
        if self.ai_provider == "openai":
            return await self._call_openai(full_prompt)
        elif self.ai_provider == "anthropic":
            return await self._call_anthropic(full_prompt)
        else:
            # Default mock response for testing
            return f"This is a placeholder response to: {user_message}"
    
    def _build_prompt(self, user_name: str, user_message: str, relevant_lore: List[str] = None) -> Dict:
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
        
        # Add knowledge base if available
        if self.knowledge_base:
            system_content += f"\n\n**Knowledge Base:**\n{self.knowledge_base}"
        
        # Add memory if available
        if self.long_term_memory:
            memory_content = "\n\n**What you remember about this conversation and the users:**\n"
            for topic, details in self.long_term_memory.items():
                memory_content += f"- {topic}: {details}\n"
            system_content += memory_content
        
        # Add relevant lorebook entries if available
        if relevant_lore and len(relevant_lore) > 0:
            lore_content = "\n\n**Relevant information for this response:**\n"
            for lore in relevant_lore:
                lore_content += f"- {lore}\n"
            system_content += lore_content
        
        messages.append({"role": "system", "content": system_content})
        
        # Add conversation history
        for entry in self.conversation_history:
            messages.append({"role": entry["role"], "content": entry["content"]})
        
        # Add current message
        messages.append({"role": "user", "content": user_message})
        
        return messages
        
    async def memory_command(self, interaction: discord.Interaction):
        """Slash command to manage memory"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
        
        # Create a view with memory management options
        view = MemoryManagementView(self)
        
        memory_display = "**Long-term Memory:**\n"
        if not self.long_term_memory:
            memory_display += "No memories stored yet."
        else:
            for topic, details in self.long_term_memory.items():
                memory_display += f"- **{topic}**: {details}\n"
        
        await interaction.response.send_message(memory_display, view=view, ephemeral=True)
        
    async def lorebook_command(self, interaction: discord.Interaction):
        """Slash command to manage lorebook entries"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
            
        # Create a modal for adding lorebook entries
        modal = LorebookEntryModal(title="Add Lorebook Entry")
        
        async def on_submit(modal_interaction):
            new_entry = {
                "keyword": modal.keyword_input.value,
                "content": modal.content_input.value
            }
            self.lorebook_entries.append(new_entry)
            await modal_interaction.response.send_message(f"Added lorebook entry for keyword: {new_entry['keyword']}", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def knowledge_command(self, interaction: discord.Interaction):
        """Slash command to manage knowledge base"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
            
        # Create a modal for editing knowledge base
        modal = KnowledgeBaseModal(title="Edit Knowledge Base", current_text=self.knowledge_base)
        
        async def on_submit(modal_interaction):
            self.knowledge_base = modal.knowledge_input.value
            await modal_interaction.response.send_message("Knowledge base updated!", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    async def voice_command(self, interaction: discord.Interaction):
        """Slash command to configure voice settings"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the bot owner can use this command", ephemeral=True)
            return
        
        # Get the voice channels in the server
        voice_channels = [channel for channel in interaction.guild.channels if isinstance(channel, discord.VoiceChannel)]
        
        # Create a select menu with voice channels
        select = discord.ui.Select(
            placeholder="Select a voice channel to join",
            options=[discord.SelectOption(label=channel.name, value=str(channel.id)) for channel in voice_channels]
        )
        
        async def select_callback(select_interaction):
            channel_id = int(select.values[0])
            channel = interaction.guild.get_channel(channel_id)
            
            # Join the voice channel
            try:
                if hasattr(self, 'voice_client') and self.voice_client is not None:
                    await self.voice_client.disconnect()
                    
                self.voice_client = await channel.connect()
                await select_interaction.response.send_message(f"Connected to voice channel: {channel.name}", ephemeral=True)
            except Exception as e:
                await select_interaction.response.send_message(f"Error connecting to voice channel: {e}", ephemeral=True)
        
        select.callback = select_callback
        
        # Create a button to disconnect from voice
        disconnect_button = discord.ui.Button(label="Disconnect from Voice", style=discord.ButtonStyle.danger)
        
        async def disconnect_callback(button_interaction):
            if hasattr(self, 'voice_client') and self.voice_client is not None:
                await self.voice_client.disconnect()
                self.voice_client = None
                await button_interaction.response.send_message("Disconnected from voice channel", ephemeral=True)
            else:
                await button_interaction.response.send_message("Not connected to a voice channel", ephemeral=True)
        
        disconnect_button.callback = disconnect_callback
        
        # Create the view and add the components
        view = discord.ui.View()
        view.add_item(select)
        view.add_item(disconnect_button)
        
        await interaction.response.send_message("Voice Channel Settings:", view=view, ephemeral=True)
    
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


class LorebookEntryModal(discord.ui.Modal):
    """Modal for adding lorebook entries"""
    def __init__(self, title: str):
        super().__init__(title=title)
        self.keyword_input = discord.ui.TextInput(
            label="Trigger Keyword:",
            placeholder="Enter the keyword that will trigger this lore",
            max_length=100
        )
        self.content_input = discord.ui.TextInput(
            label="Lore Content:",
            style=discord.TextStyle.paragraph,
            placeholder="Enter the information for this lorebook entry",
            max_length=2000
        )
        self.add_item(self.keyword_input)
        self.add_item(self.content_input)


class KnowledgeBaseModal(discord.ui.Modal):
    """Modal for editing knowledge base"""
    def __init__(self, title: str, current_text: str):
        super().__init__(title=title)
        self.knowledge_input = discord.ui.TextInput(
            label="Knowledge Base:",
            style=discord.TextStyle.paragraph,
            default=current_text,
            placeholder="Enter general knowledge for the character",
            max_length=4000
        )
        self.add_item(self.knowledge_input)


class MemoryManagementView(discord.ui.View):
    """View for managing character memory"""
    def __init__(self, bot: CharacterBot):
        super().__init__()
        self.bot = bot
        
    @discord.ui.button(label="Generate Memory", style=discord.ButtonStyle.primary)
    async def generate_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot._generate_memory()
        await interaction.response.send_message("Memory generated from recent conversations!", ephemeral=True)
    
    @discord.ui.button(label="Clear Memory", style=discord.ButtonStyle.danger)
    async def clear_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.long_term_memory = {}
        await interaction.response.send_message("Memory cleared!", ephemeral=True)
    
    @discord.ui.button(label="Toggle Auto-Memory", style=discord.ButtonStyle.secondary)
    async def toggle_auto_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.auto_memory_generation = not self.bot.auto_memory_generation
        await interaction.response.send_message(
            f"Auto memory generation: {'Enabled' if self.bot.auto_memory_generation else 'Disabled'}", 
            ephemeral=True
        )
    
    @discord.ui.button(label="Add Memory Entry", style=discord.ButtonStyle.success)
    async def add_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MemoryEntryModal()
        
        async def on_submit(modal_interaction):
            topic = modal.topic_input.value
            details = modal.details_input.value
            self.bot.long_term_memory[topic] = details
            await modal_interaction.response.send_message(f"Added memory: {topic}", ephemeral=True)
            
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)


class MemoryEntryModal(discord.ui.Modal):
    """Modal for adding memory entries"""
    def __init__(self):
        super().__init__(title="Add Memory Entry")
        self.topic_input = discord.ui.TextInput(
            label="Topic:",
            placeholder="E.g., User Preferences, Recent Events",
            max_length=100
        )
        self.details_input = discord.ui.TextInput(
            label="Details:",
            style=discord.TextStyle.paragraph,
            placeholder="Enter the details to remember",
            max_length=1000
        )
        self.add_item(self.topic_input)
        self.add_item(self.details_input)


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