import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
import re
import os
import datetime
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
import asyncio
import aiohttp
from discord.ext import tasks


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openshape")


class OpenShape(commands.Bot):
    def __init__(self, config_path: str, *args, **kwargs):
        # Load configuration
        with open(config_path, "r", encoding="utf-8") as f:
            self.character_config = json.load(f)

        # Setup intents
        intents = discord.Intents.all()

        # Initialize the bot
        super().__init__(
            command_prefix=self.character_config.get("command_prefix", "!"),
            intents=intents,
            *args,
            **kwargs,
        )

        # Set basic config
        self.config_path = config_path
        self.owner_id = self.character_config.get("owner_id")
        self.character_name = self.character_config.get("character_name", "Assistant")

        # Conversation settings
        self.system_prompt = self.character_config.get("system_prompt", "")
        self.character_description = self.character_config.get(
            "character_description", ""
        )
        self.personality_catchphrases = self.character_config.get("personality_catchphrases")
        self.personality_age = self.character_config.get("personality_age")
        self.personality_likes = self.character_config.get("personality_likes")
        self.personality_dislikes = self.character_config.get("personality_dislikes")
        self.personality_goals = self.character_config.get("personality_goals")
        self.personality_traits = self.character_config.get("personality_traits")
        self.personality_physical_traits = self.character_config.get("personality_physical_traits")
        self.personality_tone = self.character_config.get("personality_tone")
        self.personality_history = self.character_config.get("personality_history")
        self.personality_conversational_goals = self.character_config.get("personality_conversational_goals")
        self.personality_conversational_examples = self.character_config.get("personality_conversational_examples")
        self.character_scenario = self.character_config.get("character_scenario", "")
        

        # API configuration for AI integration
        self.api_settings = self.character_config.get("api_settings", {})
        self.base_url = self.api_settings.get("base_url", "")
        self.api_key = self.api_settings.get("api_key", "")
        self.chat_model = self.api_settings.get("chat_model", "")
        self.tts_model = self.api_settings.get("tts_model", "")
        self.tts_voice = self.api_settings.get("tts_voice", "")

        # Initialize OpenAI client if API settings are provided
        self.ai_client = None
        if self.api_key and self.base_url:
            try:
                self.ai_client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    max_retries=2,
                    timeout=60,
                )
                logger.info("AI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize AI client: {e}")

        # File paths for storage
        self.data_dir = self.character_config.get("data_dir", "character_data")
        self.conversations_dir = os.path.join(self.data_dir, "conversations")
        self.memory_path = os.path.join(self.data_dir, "memory.json")
        self.lorebook_path = os.path.join(self.data_dir, "lorebook.json")
        self.audio_dir = os.path.join(self.data_dir, "audio")

        # Create directories if they don't exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.conversations_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

        # Initialize storage
        self._load_storage()

        # Response behavior settings
        self.add_character_name = self.character_config.get("add_character_name", True)
        self.always_reply_mentions = self.character_config.get(
            "always_reply_mentions", True
        )
        self.reply_to_name = self.character_config.get("reply_to_name", True)
        self.activated_channels = set(
            self.character_config.get("activated_channels", [])
        )
        self.use_tts = self.character_config.get("use_tts", False)

        # Moderation settings
        self.blacklisted_users = self.character_config.get("blacklisted_users", [])
        self.blacklisted_roles = self.character_config.get("blacklisted_roles", [])
        self.conversation_timeout = self.character_config.get("conversation_timeout", 30)  # Default 30 minutes
        
        # Start the cleanup task
       

    def _load_storage(self):
        """Load memory and lorebook from files with updated memory structure"""
        # Load memory
        if os.path.exists(self.memory_path):
            with open(self.memory_path, "r", encoding="utf-8") as f:
                loaded_memory = json.load(f)
                
                # Check if we need to migrate old memory format
                if loaded_memory and isinstance(next(iter(loaded_memory.values())), str):
                    # Old format detected - migrate to new format
                    migrated_memory = {}
                    for topic, detail in loaded_memory.items():
                        migrated_memory[topic] = {
                            "detail": detail,
                            "source": "Unknown",  # Default source for migrated memories
                            "timestamp": datetime.datetime.now().isoformat()
                        }
                    self.long_term_memory = migrated_memory
                else:
                    # Already in new format or empty
                    self.long_term_memory = loaded_memory
        else:
            self.long_term_memory = {}
            self._save_memory()

        # Load lorebook (unchanged)
        if os.path.exists(self.lorebook_path):
            with open(self.lorebook_path, "r", encoding="utf-8") as f:
                self.lorebook_entries = json.load(f)
        else:
            self.lorebook_entries = []
            self._save_lorebook()

    def _save_memory(self):
        """Save memory to file"""
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.long_term_memory, f, indent=2)

    def _save_lorebook(self):
        """Save lorebook to file"""
        with open(self.lorebook_path, "w", encoding="utf-8") as f:
            json.dump(self.lorebook_entries, f, indent=2)

    def _save_config(self):
        """Save configuration to file"""
        # Update config with current settings
        self.character_config.update(
            {
                "character_name": self.character_name,
                "system_prompt": self.system_prompt,
                "character_description": self.character_description,
                 "personality_catchphrases": self.personality_catchphrases,
            "personality_age": self.personality_age,
                "personality_likes": self.personality_likes,
                "personality_dislikes": self.personality_dislikes,
                "personality_goals": self.personality_goals,
                "personality_traits": self.personality_traits,
                "personality_physical_traits": self.personality_physical_traits,
                "personality_tone": self.personality_tone,
                "personality_history": self.personality_history,
                "personality_conversational_goals": self.personality_conversational_goals,
                "personality_conversational_examples": self.personality_conversational_examples,
                "character_scenario": self.character_scenario,
                "add_character_name": self.add_character_name,
                "reply_to_name": self.reply_to_name,
                "always_reply_mentions": self.always_reply_mentions,
                "activated_channels": list(self.activated_channels),
                "blacklisted_users": self.blacklisted_users,
                "blacklisted_roles": self.blacklisted_roles,
            }
        )

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.character_config, f, indent=2)

    def _save_conversation(self, channel_id, conversation):
        """Save a conversation to a JSON file"""
        # Create a filename with channel ID and timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{channel_id}_{timestamp}.json"
        filepath = os.path.join(self.conversations_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(conversation, f, indent=2)

    # Add a task loop to clean up old conversations
    @tasks.loop(minutes=5)  # Check every 5 minutes
    async def conversation_cleanup(self):
        """Task to clean up old conversations that haven't been active recently"""
        if not hasattr(self, "channel_conversations"):
            return
        
        current_time = datetime.datetime.now()
        channels_to_cleanup = []
        
        # Find channels with inactive conversations
        for channel_id, conversation in self.channel_conversations.items():
            if not conversation:
                continue
                
            # Get timestamp from last message
            try:
                last_message = conversation[-1]
                last_timestamp = last_message.get("timestamp")
                
                if last_timestamp:
                    last_time = datetime.datetime.fromisoformat(last_timestamp)
                    time_diff = current_time - last_time
                    
                    # If conversation is older than timeout, mark for cleanup
                    if time_diff.total_seconds() > (self.conversation_timeout * 60):
                        channels_to_cleanup.append(channel_id)
                        logger.info(f"Cleaning up conversation in channel {channel_id} - inactive for {time_diff.total_seconds()/60:.1f} minutes")
            except (ValueError, KeyError, IndexError) as e:
                logger.error(f"Error processing conversation timestamps: {e}")
        
        # Clean up the inactive conversations
        for channel_id in channels_to_cleanup:
            del self.channel_conversations[channel_id]

    async def setup_hook(self):
        """Register slash commands when the bot is starting up"""
        self.conversation_cleanup.start()
        # Basic commands
        self.tree.add_command(
            app_commands.Command(
                name="api_settings",
                description="Configure AI API settings",
                callback=self.api_settings_command,
            ),
        )

        self.tree.add_command(
            app_commands.Command(
                name="character_info",
                description="Show information about this character",
                callback=self.character_info_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="activate",
                description="Activate the bot to respond to all messages in the channel",
                callback=self.activate_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="deactivate",
                description="Deactivate the bot's automatic responses in the channel",
                callback=self.deactivate_command,
            )
        )

        # Memory and knowledge commands
        self.tree.add_command(
            app_commands.Command(
                name="memory",
                description="View or manage the character's memory",
                callback=self.memory_command,
            )
        )

        self.tree.add_command(
            app_commands.Command(
                name="lorebook",
                description="Manage lorebook entries",
                callback=self.lorebook_command,
            )
        )

        # Settings command
        self.tree.add_command(
            app_commands.Command(
                name="settings",
                description="Manage character settings",
                callback=self.settings_command,
            )
        )
        self.tree.add_command(
            app_commands.Command(
                name="edit_personality_traits",
                description="Edit specific personality traits for the character",
                callback=self.edit_personality_traits_command,
            ),
        )
        
        self.tree.add_command(
            app_commands.Command(
                name="edit_backstory",
                description="Edit the character's history and background",
                callback=self.edit_backstory_command,
            ),
        )
        
        self.tree.add_command(
            app_commands.Command(
                name="edit_preferences",
                description="Edit what the character likes and dislikes",
                callback=self.edit_preferences_command,
            ),
        )
        # 
        self.tree.add_command(
            app_commands.Command(
                name="sleep_command",
                description="Generate a long term memory.",
                callback=self.sleep_command,
            ),
        )
        # Configuration commands (owner only)
        for guild_id in self.character_config.get("allowed_guilds", []):
            guild = discord.Object(id=guild_id)

            self.tree.add_command(
                app_commands.Command(
                    name="edit_prompt",
                    description="Edit the character's system prompt",
                    callback=self.edit_prompt_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="edit_description",
                    description="Edit the character's description",
                    callback=self.edit_description_command,
                ),
                guild=guild,
            )


            self.tree.add_command(
                app_commands.Command(
                    name="edit_scenario",
                    description="Edit the character's scenario",
                    callback=self.edit_scenario_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="blacklist",
                    description="Add or remove a user from the blacklist",
                    callback=self.blacklist_command,
                ),
                guild=guild,
            )

            self.tree.add_command(
                app_commands.Command(
                    name="save",
                    description="Save all current settings and data",
                    callback=self.save_command,
                ),
                guild=guild,
            )

    async def character_info_command(self, interaction: discord.Interaction):
        """Public command to show character information"""
        embed = discord.Embed(title=f"{self.character_name} Info", color=0x3498DB)
        
        # Basic info (existing)
        embed.add_field(
            name="Description",
            value=self.character_description[:1024] or "No description set",
            inline=False,
        )
        if self.character_scenario:
            embed.add_field(
                name="Scenario", value=self.character_scenario[:1024], inline=False
            )
        
        # Add new personality details if available
        if self.personality_age:
            embed.add_field(name="Age", value=self.personality_age, inline=True)
        
        if self.personality_traits:
            embed.add_field(name="Traits", value=self.personality_traits, inline=True)
            
        if self.personality_likes:
            embed.add_field(name="Likes", value=self.personality_likes, inline=True)
            
        if self.personality_dislikes:
            embed.add_field(name="Dislikes", value=self.personality_dislikes, inline=True)
        
        if self.personality_tone:
            embed.add_field(name="Tone", value=self.personality_tone, inline=True)
        
        # Add a field for history if it exists
        if self.personality_history:
            # Truncate if too long
            history = self.personality_history[:1024] + ("..." if len(self.personality_history) > 1024 else "")
            embed.add_field(name="History", value=history, inline=False)

        await interaction.response.send_message(embed=embed)

    async def activate_command(self, interaction: discord.Interaction):
        """Activate the bot in the current channel"""
        self.activated_channels.add(interaction.channel_id)
        self._save_config()
        await interaction.response.send_message(
            f"{self.character_name} will now respond to all messages in this channel."
        )

    async def deactivate_command(self, interaction: discord.Interaction):
        """Deactivate the bot in the current channel"""
        if interaction.channel_id in self.activated_channels:
            self.activated_channels.remove(interaction.channel_id)
            self._save_config()
        await interaction.response.send_message(
            f"{self.character_name} will now only respond when mentioned or called by name."
        )

    async def edit_personality_traits_command(self, interaction: discord.Interaction):
        """Edit the character's specific personality traits"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create dropdown for selecting which trait to edit
        options = [
            discord.SelectOption(label="Catchphrases", value="catchphrases"),
            discord.SelectOption(label="Age", value="age"),
            discord.SelectOption(label="Traits", value="traits"),
            discord.SelectOption(label="Physical Traits", value="physical"),
            discord.SelectOption(label="Tone", value="tone"),
            discord.SelectOption(label="Conversational Style", value="style"),
        ]

        select = discord.ui.Select(placeholder="Select trait to edit", options=options)

        async def select_callback(select_interaction):
            trait = select.values[0]
            
            current_values = {
                "catchphrases": self.personality_catchphrases,
                "age": self.personality_age,
                "traits": self.personality_traits,
                "physical": self.personality_physical_traits,
                "tone": self.personality_tone,
                "style": self.personality_conversational_examples
            }
            
            # Create modal for editing
            modal = TextEditModal(
                title=f"Edit {trait.title()}", 
                current_text=current_values[trait] or ""
            )

            async def on_submit(modal_interaction):
                # Update the appropriate field
                if trait == "catchphrases":
                    self.personality_catchphrases = modal.text_input.value
                elif trait == "age":
                    self.personality_age = modal.text_input.value
                elif trait == "traits":
                    self.personality_traits = modal.text_input.value
                elif trait == "physical":
                    self.personality_physical_traits = modal.text_input.value
                elif trait == "tone":
                    self.personality_tone = modal.text_input.value
                elif trait == "style":
                    self.personality_conversational_examples = modal.text_input.value
                    
                self._save_config()
                await modal_interaction.response.send_message(
                    f"Character {trait} updated!", ephemeral=True
                )

            modal.on_submit = on_submit
            await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            "Select a personality trait to edit:", view=view, ephemeral=True
        )

    async def edit_backstory_command(self, interaction: discord.Interaction):
        """Edit the character's history"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
        modal = TextEditModal(
            title="Edit Character History", 
            current_text=self.personality_history or ""
        )

        async def on_submit(modal_interaction):
            self.personality_history = modal.text_input.value
            self._save_config()
            await modal_interaction.response.send_message(
                "Character history updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    async def edit_preferences_command(self, interaction: discord.Interaction):
        """Edit what the character likes and dislikes"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create dropdown to select likes or dislikes
        options = [
            discord.SelectOption(label="Likes", value="likes"),
            discord.SelectOption(label="Dislikes", value="dislikes"),
            discord.SelectOption(label="Goals", value="goals"),
        ]

        select = discord.ui.Select(placeholder="Select preference to edit", options=options)

        async def select_callback(select_interaction):
            pref = select.values[0]
            
            current_values = {
                "likes": self.personality_likes,
                "dislikes": self.personality_dislikes,
                "goals": self.personality_goals
            }
            
            # Create modal for editing
            modal = TextEditModal(
                title=f"Edit {pref.title()}", 
                current_text=current_values[pref] or ""
            )

            async def on_submit(modal_interaction):
                # Update the appropriate field
                if pref == "likes":
                    self.personality_likes = modal.text_input.value
                elif pref == "dislikes":
                    self.personality_dislikes = modal.text_input.value
                elif pref == "goals":
                    self.personality_goals = modal.text_input.value
                    
                self._save_config()
                await modal_interaction.response.send_message(
                    f"Character {pref} updated!", ephemeral=True
                )

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            "Select preferences to edit:", view=view, ephemeral=True
        )
        
    async def sleep_command(self, interaction: discord.Interaction):
        """Process recent messages to extract and store memories before going to sleep"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return
        
        await interaction.response.defer(thinking=True)
        
        # First, acknowledge the command
        await interaction.followup.send(f"{self.character_name} is analyzing recent conversations and going to sleep...")
        
        try:
            # Fetch recent messages from the channel (up to 30)
            recent_messages = []
            async for message in interaction.channel.history(limit=30):
                # Skip system messages and bot's own messages
                if message.author.bot and message.author.id != self.user.id:
                    continue
                
                # Add message to our list
                recent_messages.append({
                    "author": message.author.display_name,
                    "content": message.content,
                    "id": message.id,
                    "timestamp": message.created_at.isoformat()
                })
            
            # Sort messages by timestamp (oldest first)
            recent_messages.sort(key=lambda m: m["timestamp"])
            
            # We don't want to process all messages individually as that would be inefficient
            # Instead, we'll batch them in small conversations
            
            # First, let's group messages by author over short time spans
            batched_conversations = []
            current_batch = []
            last_author = None
            
            for msg in recent_messages:
                # If this is a new author or the batch is getting too big, start a new batch
                if last_author != msg["author"] or len(current_batch) >= 5:
                    if current_batch:
                        batched_conversations.append(current_batch)
                    current_batch = [msg]
                else:
                    current_batch.append(msg)
                
                last_author = msg["author"]
            
            # Add the final batch if it exists
            if current_batch:
                batched_conversations.append(current_batch)
            
            # Now process each batch to extract memories
            memories_created = 0
            
            for batch in batched_conversations:
                # Skip if this is just the bot talking
                if all(msg["author"] == self.character_name for msg in batch):
                    continue
                
                # Construct a conversation to analyze
                conversation_content = ""
                for msg in batch:
                    conversation_content += f"{msg['author']}: {msg['content']}\n"
                
                # Check if this conversation has substance (more than just a greeting or short message)
                if len(conversation_content.split()) < 10:
                    continue
                
                # Extract memories from this conversation batch
                created = await self._extract_memories_from_text(conversation_content)
                memories_created += created
                
                # Throttle requests to avoid rate limits
                await asyncio.sleep(0.5)
            
            # Send a summary of what happened
            if memories_created > 0:
                response = f"{self.character_name} has processed the recent conversations and created {memories_created} new memories!"
            else:
                response = f"{self.character_name} analyzed the conversations but didn't find any significant information to remember."
                
            await interaction.channel.send(response)
            
        except Exception as e:
            logger.error(f"Error during sleep command: {e}")
            await interaction.channel.send(f"Something went wrong while processing recent messages: {str(e)[:100]}...")
            
    async def _extract_memories_from_text(self, text_content):
        """Extract and store important information from any text as memories"""
        if not self.ai_client or not self.chat_model:
            return 0
        
        try:
            # Create a system prompt for memory extraction
            system_prompt = """You are an AI designed to extract meaningful information from conversations or text that would be valuable to remember for future interactions.

            Instructions:
            1. Analyze the provided text.
            2. Identify significant information such as:
               - Personal preferences (likes, dislikes)
               - Background information (job, location, family)
               - Important events (past or planned)
               - Goals or needs expressed
               - Problems being faced
               - Relationships between people

            3. For each piece of significant information, output a JSON object with these key-value pairs:
               - "topic": A short, descriptive topic name (e.g., "User's Job", "Birthday Plans")
               - "detail": A concise factual statement summarizing what to remember
               - "importance": A number from 1-10 indicating how important this memory is (10 being most important)

            4. Format your output as a JSON array of these objects.
            5. If nothing significant was found, return an empty array: []

            Only extract specific, factual information, and focus on details that would be useful to remember in future conversations.
            Your output should be ONLY a valid JSON array with no additional text.
            """
            
            # Call API to analyze conversation
            memory_analysis = await self._call_chat_api(
                text_content,
                system_prompt=system_prompt
            )
            
            # Process the response to extract memory information
            try:
                # Look for JSON in the response (in case there's any non-JSON text)
                import re
                json_match = re.search(r'\[.*\]', memory_analysis, re.DOTALL)
                
                if json_match:
                    memory_json = json_match.group(0)
                    memory_data = json.loads(memory_json)
                    
                    # Track how many memories we created
                    memories_created = 0
                    
                    # Update memory with extracted information
                    for memory in memory_data:
                        topic = memory.get("topic")
                        detail = memory.get("detail")
                        importance = memory.get("importance", 5)
                        
                        if topic and detail and importance >= 3:  # Only store memories with importance >= 3
                            # Store memory with system attribution
                            self.long_term_memory[topic] = {
                                "detail": detail,
                                "source": "Sleep Analysis",
                                "timestamp": datetime.datetime.now().isoformat(),
                                "importance": importance
                            }
                            logger.info(f"Added memory from sleep: {topic}: {detail} (importance: {importance})")
                            memories_created += 1
                    
                    # Save memory if anything was added
                    if memories_created > 0:
                        self._save_memory()
                    
                    return memories_created
                else:
                    logger.info("No memory-worthy information found in sleep analysis")
                    return 0
                    
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Failed to parse memory response in sleep: {memory_analysis[:100]}... Error: {str(e)}")
                return 0
                
        except Exception as e:
            logger.error(f"Error in sleep memory extraction: {e}")
            return 0
    async def memory_command(self, interaction: discord.Interaction):
        """View or manage memories with source attribution"""
        # Only allow the owner to manage memories
        if interaction.user.id != self.owner_id:
            memory_display = "**Long-term Memory:**\n"
            if not self.long_term_memory:
                memory_display += "No memories stored yet."
            else:
                for topic, memory_data in self.long_term_memory.items():
                    detail = memory_data["detail"]
                    source = memory_data["source"]
                    memory_display += f"- **{topic}**: {detail} (from {source})\n"

            await interaction.response.send_message(memory_display)
            return

        # Create a view for memory management
        view = MemoryManagementView(self)

        memory_display = "**Long-term Memory:**\n"
        if not self.long_term_memory:
            memory_display += "No memories stored yet."
        else:
            for topic, memory_data in self.long_term_memory.items():
                detail = memory_data["detail"]
                source = memory_data["source"]
                memory_display += f"- **{topic}**: {detail} (from {source})\n"

        await interaction.response.send_message(memory_display, view=view)

    async def api_settings_command(self, interaction: discord.Interaction):
        """Configure AI API settings"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create a selection menu for API settings actions
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
                # Hide API key for security
                masked_key = "••••••" + self.api_key[-4:] if self.api_key else "Not set"
                settings_info = f"**API Settings:**\n"
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
                self.character_config["use_tts"] = self.use_tts
                self._save_config()
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
                    # Test chat completion
                    completion = await self._call_chat_api(
                        "Hello, this is a test message."
                    )

                    if completion:
                        await select_interaction.followup.send(
                            f"API connection successful!\nTest response: {completion[:100]}...",
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
                # Create modal for setting value
                modal = APISettingModal(title=f"Set {action.replace('_', ' ').title()}")

                async def on_submit(modal_interaction):
                    value = modal.setting_input.value

                    # Update the appropriate setting
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

                    # Update config and reinitialize client
                    self.character_config["api_settings"] = self.api_settings
                    self._save_config()

                    # Reinitialize OpenAI client if base URL and API key are set
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

    def _search_memory(self, message_content: str) -> List[str]:
        """
        Search for memories relevant to the current message content.
        Uses more sophisticated matching to find relevant memories.
        Now includes source attribution in the returned memory strings.
        
        Args:
            message_content: The user's message content
            
        Returns:
            List of relevant memory strings in format "Topic: Detail (from Source)"
        """
        if not self.long_term_memory:
            return []
            
        memory_matches = []
        message_lower = message_content.lower().split()
        
        # Score each memory for relevance
        memory_scores = {}
        
        for topic, memory_data in self.long_term_memory.items():
            score = 0
            topic_lower = topic.lower()
            detail = memory_data["detail"]
            source = memory_data["source"]
            
            # Direct topic match (highest priority)
            if topic_lower in message_content.lower():
                score += 10
                
            # Word-level matching
            topic_words = topic_lower.split()
            for word in topic_words:
                if len(word) > 3 and word in message_lower:  # Only match significant words
                    score += 3
                    
            # Look for words from the detail in the message
            detail_words = set(detail.lower().split())
            for word in detail_words:
                if len(word) > 3 and word in message_lower:
                    score += 1
                    
            # If we found any relevance, add to potential matches
            if score > 0:
                formatted_memory = f"{topic}: {detail} (from {source})"
                memory_scores[topic] = (score, formatted_memory)
        
        # Sort by relevance score (highest first)
        sorted_memories = sorted(memory_scores.items(), key=lambda x: x[1][0], reverse=True)
        
        # Get the memory strings for the top matches (limit to 3 most relevant)
        memory_matches = [mem[1][1] for mem in sorted_memories[:3]]
        
        # Log what we found
        if memory_matches:
            logger.info(f"Found {len(memory_matches)} relevant memories: {[m.split(':')[0] for m in memory_matches]}")
        
        return memory_matches
    
    
    async def _call_chat_api(
        self,
        user_message,
        user_name="User",
        conversation_history=None,
        relevant_info=None,
        system_prompt=None,
    ):
        """Call the AI API to generate a response with limited conversation history and relevant memories"""
        if not self.ai_client or not self.chat_model:
            return None

        try:
            # Use provided system prompt or build default one
            if system_prompt:
                system_content = system_prompt
            else:
                # Build system prompt with character info
                system_content = f"""You are {self.character_name}.
                    Description: {self.character_description}
                    Scenario: {self.character_scenario}
                    """
                if self.personality_age:
                    system_content += f"Age: {self.personality_age}\n"     
                if self.personality_traits:
                    system_content += f"Character Traits: {self.personality_traits}\n"
                if self.personality_physical_traits:
                    system_content += f"Physical Traits: {self.personality_physical_traits}\n"
                if self.personality_tone:
                    system_content += f"Speaking Tone: {self.personality_tone}\n"
                if self.personality_likes:
                    system_content += f"Likes: {self.personality_likes}\n"
                if self.personality_dislikes:
                    system_content += f"Dislikes: {self.personality_dislikes}\n"
                if self.personality_goals:
                    system_content += f"Goals: {self.personality_goals}\n"
                if self.personality_history:
                    system_content += f"Background: {self.personality_history}\n"
                if self.personality_catchphrases:
                    system_content += f"Signature Phrases: {self.personality_catchphrases}\n"
                    
                # Add conversational examples with substitution
                if self.personality_conversational_examples:
                    examples = self.personality_conversational_examples.replace("{user}", user_name)
                    system_content += f"\nExample Interactions:\n{examples}\n"
                    
                # Add conversational goals with substitution
                if self.personality_conversational_goals:
                    goals = self.personality_conversational_goals.replace("{user}", user_name)
                    system_content += f"\nConversational Goals: {goals}\n"

            # Add custom system prompt if available
            if self.system_prompt:
                system_content = f"{self.system_prompt}\n\n{system_content}"

            # Add relevant information (lore and memories) if available
            if relevant_info and len(relevant_info) > 0:
                system_content += "\nImportant information you know:\n"
                for info in relevant_info:
                    system_content += f"- {info}\n"

            # Prepare messages list
            messages = [{"role": "system", "content": system_content}]

            # Add conversation history (limited to available history, max 8 messages)
            if conversation_history:
                history_to_use = conversation_history[-8:] if len(conversation_history) > 8 else conversation_history
                for entry in history_to_use:
                    role = "assistant" if entry["role"] == "assistant" else "user"
                    messages.append({"role": role, "content": entry["content"]})

            # If the latest message isn't in history, add it
            if not conversation_history or user_message != conversation_history[-1].get("content", ""):
                messages.append({"role": "user", "content": user_message})

            # Call API
            completion = await self.ai_client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                stream=False,
            )

            # Extract response text
            response = completion.choices[0].message.content
            return response

        except Exception as e:
            logger.error(f"Error calling chat API: {e}")
            return f"I'm having trouble connecting to my thoughts right now. Please try again later. (Error: {str(e)[:50]}...)"


    def _extract_speech_text(self, text, ignore_asterisks=False, only_narrate_quotes=False):
        result = text
        if ignore_asterisks:
            result = re.sub(r'\*[^*]*\*', '', result)
        
        if only_narrate_quotes:
            # Extract only text within quotes
            quotes = re.findall(r'"([^"]*)"', result)
            if quotes:
                # Join all quoted text with appropriate pauses
                result = '... '.join(quotes)
            else:
                # If no quotes found, return empty string or original based on preference
                result = ''
        
        # Clean up any extra whitespace
        result = ' '.join(result.split())
    
        return result

    # Add a method to generate TTS audio
    async def _generate_tts(self, text):
        """Generate TTS audio from text"""
        if (
            not self.ai_client
            or not self.tts_model
            or not self.tts_voice
            or not self.use_tts
        ):
            return None

        try:
            speech_text = self._extract_speech_text(
                text, 
                ignore_asterisks=True,
                only_narrate_quotes=True
            )
            
            if not speech_text:
                return None
            
            # Generate a filename based on text hash
            import hashlib

            text_hash = hashlib.md5(text.encode()).hexdigest()[:10]
            filename = f"{self.character_name}_{text_hash}.mp3"
            filepath = os.path.join(self.audio_dir, filename)

            # Check if file already exists
            if os.path.exists(filepath):
                return filepath

            # Call TTS API
            response = await self.ai_client.audio.speech.create(
                model=self.tts_model, voice=self.tts_voice, input=speech_text
            )

            # Save audio file
            response.stream_to_file(filepath)
            return filepath

        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None

    # Modify the _generate_res
    async def lorebook_command(self, interaction: discord.Interaction):
        """Manage lorebook entries"""
        # Check if user is owner for management
        if interaction.user.id != self.owner_id:
            if not self.lorebook_entries:
                await interaction.response.send_message(
                    "No lorebook entries exist yet."
                )
                return

            # Show lorebook entries to non-owners
            lore_embeds = []
            for entry in self.lorebook_entries:
                embed = discord.Embed(
                    title=f"Lorebook: {entry['keyword']}",
                    description=entry["content"],
                    color=0x9B59B6,
                )
                lore_embeds.append(embed)

            await interaction.response.send_message(embeds=lore_embeds)
            return

        # Create a view for lorebook management
        view = LorebookManagementView(self)

        lore_display = "**Lorebook Entries:**\n"
        if not self.lorebook_entries:
            lore_display += "No entries yet."
        else:
            for i, entry in enumerate(self.lorebook_entries):
                lore_display += (
                    f"{i+1}. **{entry['keyword']}**: {entry['content'][:50]}...\n"
                )

        await interaction.response.send_message(lore_display, view=view)

    async def settings_command(self, interaction: discord.Interaction):
        """Display and modify bot settings"""
        # Only allow the owner to change settings
        if interaction.user.id != self.owner_id:
            settings_display = f"**{self.character_name} Settings:**\n"
            settings_display += f"- Add name to responses: {'Enabled' if self.add_character_name else 'Disabled'}\n"
            settings_display += f"- Reply to mentions: {'Enabled' if self.always_reply_mentions else 'Disabled'}\n"
            settings_display += f"- Reply when name is called: {'Enabled' if self.reply_to_name else 'Disabled'}\n"

            await interaction.response.send_message(settings_display)
            return

        # Create a view with settings toggles
        view = SettingsView(self)

        settings_display = f"**{self.character_name} Settings:**\n"
        settings_display += f"- Add name to responses: {'Enabled' if self.add_character_name else 'Disabled'}\n"
        settings_display += f"- Reply to mentions: {'Enabled' if self.always_reply_mentions else 'Disabled'}\n"
        settings_display += f"- Reply when name is called: {'Enabled' if self.reply_to_name else 'Disabled'}\n"

        await interaction.response.send_message(settings_display, view=view)

    async def edit_prompt_command(self, interaction: discord.Interaction):
        """Edit the character's system prompt"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
        modal = TextEditModal(
            title="Edit System Prompt", current_text=self.system_prompt
        )

        async def on_submit(modal_interaction):
            self.system_prompt = modal.text_input.value
            self._save_config()
            await modal_interaction.response.send_message(
                "System prompt updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    async def edit_description_command(self, interaction: discord.Interaction):
        """Edit the character's description"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
        modal = TextEditModal(
            title="Edit Description", current_text=self.character_description
        )

        async def on_submit(modal_interaction):
            self.character_description = modal.text_input.value
            self._save_config()
            await modal_interaction.response.send_message(
                "Character description updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)


    async def edit_scenario_command(self, interaction: discord.Interaction):
        """Edit the character's scenario"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create modal for editing
        modal = TextEditModal(
            title="Edit Scenario", current_text=self.character_scenario
        )

        async def on_submit(modal_interaction):
            self.character_scenario = modal.text_input.value
            self._save_config()
            await modal_interaction.response.send_message(
                "Character scenario updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    async def blacklist_command(self, interaction: discord.Interaction):
        """Add or remove a user from blacklist"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Create a selection menu for blacklist actions
        options = [
            discord.SelectOption(label="View Blacklist", value="view"),
            discord.SelectOption(label="Add User", value="add_user"),
            discord.SelectOption(label="Remove User", value="remove_user"),
        ]

        select = discord.ui.Select(placeholder="Select Action", options=options)

        async def select_callback(select_interaction):
            action = select.values[0]

            if action == "view":
                if not self.blacklisted_users:
                    await select_interaction.response.send_message(
                        "No users are blacklisted.", ephemeral=True
                    )
                    return

                blacklist_display = "**Blacklisted Users:**\n"
                for user_id in self.blacklisted_users:
                    user = self.get_user(user_id)
                    name = user.name if user else f"Unknown User ({user_id})"
                    blacklist_display += f"- {name} ({user_id})\n"

                await select_interaction.response.send_message(
                    blacklist_display, ephemeral=True
                )

            elif action == "add_user":
                # Create modal for adding user ID
                modal = UserIDModal(title="Add User to Blacklist")

                async def on_user_submit(modal_interaction):
                    try:
                        user_id = int(modal.user_id_input.value)
                        if user_id not in self.blacklisted_users:
                            self.blacklisted_users.append(user_id)
                            self._save_config()
                            await modal_interaction.response.send_message(
                                f"User {user_id} added to blacklist.", ephemeral=True
                            )
                        else:
                            await modal_interaction.response.send_message(
                                "User is already blacklisted.", ephemeral=True
                            )
                    except ValueError:
                        await modal_interaction.response.send_message(
                            "Invalid user ID. Please enter a valid number.",
                            ephemeral=True,
                        )

                modal.on_submit = on_user_submit
                await select_interaction.response.send_modal(modal)

            elif action == "remove_user":
                if not self.blacklisted_users:
                    await select_interaction.response.send_message(
                        "No users are blacklisted.", ephemeral=True
                    )
                    return

                # Create modal for removing user ID
                modal = UserIDModal(title="Remove User from Blacklist")

                async def on_user_submit(modal_interaction):
                    try:
                        user_id = int(modal.user_id_input.value)
                        if user_id in self.blacklisted_users:
                            self.blacklisted_users.remove(user_id)
                            self._save_config()
                            await modal_interaction.response.send_message(
                                f"User {user_id} removed from blacklist.",
                                ephemeral=True,
                            )
                        else:
                            await modal_interaction.response.send_message(
                                "User is not in the blacklist.", ephemeral=True
                            )
                    except ValueError:
                        await modal_interaction.response.send_message(
                            "Invalid user ID. Please enter a valid number.",
                            ephemeral=True,
                        )

                modal.on_submit = on_user_submit
                await select_interaction.response.send_modal(modal)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            "Blacklist Management:", view=view, ephemeral=True
        )

    async def save_command(self, interaction: discord.Interaction):
        """Save all data and configuration"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return

        # Save everything
        self._save_config()
        self._save_memory()
        self._save_lorebook()

        await interaction.response.send_message(
            "All data and settings saved!", ephemeral=True
        )

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        await self.tree.sync()
        logger.info(f"Character name: {self.character_name}")

    async def on_message(self, message: discord.Message):
        """Process incoming messages and respond if appropriate"""
        # Ignore own messages
        if message.author == self.user:
            return

        # Process commands with prefix
        await self.process_commands(message)

        # Check if user is blacklisted
        if message.author.id in self.blacklisted_users:
            return

        # Check if we should respond
        should_respond = False

        # Check if the channel is activated for responding to all messages
        if message.channel.id in self.activated_channels:
            should_respond = True

        # Respond to direct mentions
        elif self.always_reply_mentions and self.user in message.mentions:
            should_respond = True

        # Respond when name is called
        elif (
            self.reply_to_name
            and self.character_name.lower() in message.content.lower()
        ):
            should_respond = True

        # Check for OOC command prefix (out of character)
        is_ooc = message.content.startswith("//") or message.content.startswith("/ooc")
        if is_ooc and message.author.id == self.owner_id:
            await self._handle_ooc_command(message)
            return

        if should_respond:
            async with message.channel.typing():
                # Remove mentions from the message
                clean_content = re.sub(r"<@!?(\d+)>", "", message.content).strip()

                # Get conversation history for this channel (limited to 8 messages)
                channel_history = self._get_channel_conversation(message.channel.id)
                
                # Add the new message to history
                channel_history.append(
                    {
                        "role": "user",
                        "name": message.author.display_name,
                        "content": clean_content,
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                )
                
                # Ensure we maintain the 8 message limit
                if len(channel_history) > 8:
                    channel_history = channel_history[-8:]

                # Get relevant lorebook entries
                relevant_lore = self._get_relevant_lorebook_entries(clean_content)
                
                # Get relevant memories using our new search function
                relevant_memories = self._search_memory(clean_content)
                
                # Combine lore and memories into single relevant_info list
                relevant_info = []
                if relevant_lore:
                    relevant_info.extend(relevant_lore)
                if relevant_memories:
                    relevant_info.extend(relevant_memories)

                # Generate a response based on persona, history and relevant information
                response = await self._generate_response(
                    message.author.display_name,
                    clean_content,
                    channel_history,
                    relevant_info,
                )

                # Add response to history
                channel_history.append(
                    {
                        "role": "assistant",
                        "name": self.character_name,
                        "content": response,
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                )
                
                # Again, ensure we maintain the 8 message limit
                if len(channel_history) > 8:
                    channel_history = channel_history[-8:]

                # Update memory if there's something important to remember
                await self._update_memory_from_conversation(
                    message.author.display_name, clean_content, response
                )

                # Save conversation periodically
                # Note: Changed to save every time since we're limiting to 8 messages anyway
                self._save_conversation(message.channel.id, channel_history)

                # Format response with name if enabled
                formatted_response = (
                    f"**{self.character_name}**: {response}"
                    if self.add_character_name
                    else response
                )
                
                # Generate and send TTS if enabled AND user is in a voice channel
                if self.use_tts and message.guild and message.author.voice and message.author.voice.channel:
                    try:
                        # Generate TTS directly without saving to a permanent file
                        temp_audio_file = await self._generate_temp_tts(response)
                        if temp_audio_file:
                            voice_channel = message.author.voice.channel

                            # Connect to voice channel
                            voice_client = message.guild.voice_client
                            if voice_client:
                                if voice_client.channel != voice_channel:
                                    await voice_client.move_to(voice_channel)
                            else:
                                voice_client = await voice_channel.connect()

                            # Play audio and set up cleanup
                            def after_playing(error):
                                # Delete the temporary file after it's been played
                                try:
                                    os.remove(temp_audio_file)
                                    logger.info(f"Deleted temporary TTS file: {temp_audio_file}")
                                except Exception as e:
                                    logger.error(f"Error deleting temporary TTS file: {e}")
                                
                                # Disconnect from voice channel
                                asyncio.run_coroutine_threadsafe(
                                    self._disconnect_after_audio(voice_client),
                                    self.loop,
                                )

                            voice_client.play(
                                discord.FFmpegPCMAudio(temp_audio_file),
                                after=after_playing,
                            )
                    except Exception as e:
                        logger.error(f"Error playing TTS audio: {e}")
                else:
                    # Send the response in text form
                    sent_message, message_group = await self._send_long_message(
                        message.channel,
                        formatted_response,
                        reference=message,
                        reply=True
                    )

                    # Add reactions only to the primary message
                    await sent_message.add_reaction("🗑️")
                    await sent_message.add_reaction("♻️")

                    # Store context for regeneration
                    if not hasattr(self, "message_contexts"):
                        self.message_contexts = {}

                    # Save the context needed for regeneration - save it for all message parts
                    primary_id = message_group["primary_id"]
                    if primary_id:
                        self.message_contexts[primary_id] = {
                            "user_name": message.author.display_name,
                            "user_message": clean_content,
                            "channel_history": channel_history[:-1],  # Don't include the bot's response
                            "relevant_info": relevant_info,  # Store combined lore and memories
                            "original_message": message.id  # Store original message ID for reply
                        }
    
    
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle reactions to messages with improved recycling emoji behavior"""
        # Ignore bot's own reaction adds
        if user.id == self.user.id:
            return
            
        # Get message ID to check if it's part of a multipart message
        message_id = reaction.message.id
        message_group = None
        
        # Check if this message is part of a multipart message group
        if hasattr(self, "multipart_messages") and message_id in self.multipart_messages:
            message_group = self.multipart_messages[message_id]
        
        # If the reaction is the trash emoji on the bot's message
        if (
            reaction.emoji == "🗑️"
            and reaction.message.author == self.user
            and (
                user.id == self.owner_id
                or (
                    hasattr(reaction.message, "reference")
                    and reaction.message.reference
                    and reaction.message.reference.resolved
                    and user.id == reaction.message.reference.resolved.author.id
                )
            )
        ):
            # If it's a multipart message, delete all parts
            if message_group and message_group["is_multipart"]:
                for msg_id in message_group["message_ids"]:
                    try:
                        # Try to fetch and delete each message
                        msg = await reaction.message.channel.fetch_message(msg_id)
                        await msg.delete()
                    except (discord.NotFound, discord.HTTPException):
                        # Message may already be deleted or not found
                        continue
                        
                # Clean up the multipart_messages entries
                for msg_id in message_group["message_ids"]:
                    if msg_id in self.multipart_messages:
                        del self.multipart_messages[msg_id]
            else:
                # Single message, just delete it
                await reaction.message.delete()
            
        # If the reaction is the recycle emoji (♻️) on the bot's message
        elif (
            reaction.emoji == "♻️"
            and reaction.message.author == self.user
        ):
            # Only allow if:
            # 1. User is the original message author (the one the bot replied to)
            # 2. Message doesn't have a "regenerated" flag
            is_original_author = (
                hasattr(reaction.message, "reference")
                and reaction.message.reference
                and reaction.message.reference.resolved
                and user.id == reaction.message.reference.resolved.author.id
            )
            
            # Check for regeneration flag (added as a reaction by the bot)
            already_regenerated = any(r.emoji == "🔄" and r.me for r in reaction.message.reactions)
            
            if is_original_author and not already_regenerated:
                # Determine which message ID to use for context lookup
                context_message_id = message_id
                if message_group and message_group["primary_id"]:
                    context_message_id = message_group["primary_id"]
                    
                # Check if we have the context stored for regeneration
                if hasattr(self, "message_contexts") and context_message_id in self.message_contexts:
                    context = self.message_contexts[context_message_id]
                    
                    # Show typing indicator
                    async with reaction.message.channel.typing():
                        # Get a new response with the saved context
                        new_response = await self._generate_response(
                            context["user_name"],
                            context["user_message"],
                            context["channel_history"],
                            context["relevant_info"]  # Use the saved relevant_info (lore + memories)
                        )
                        
                        # Format response with name if enabled
                        formatted_response = (
                            f"**{self.character_name}**: {new_response}"
                            if self.add_character_name
                            else new_response
                        )
                        
                        # Handle multipart messages differently
                        if message_group and message_group["is_multipart"]:
                            # Delete all the old messages first
                            for msg_id in message_group["message_ids"]:
                                try:
                                    msg = await reaction.message.channel.fetch_message(msg_id)
                                    await msg.delete()
                                except (discord.NotFound, discord.HTTPException):
                                    continue
                            
                            # Get the original message
                            try:
                                original_message = await reaction.message.channel.fetch_message(context["original_message"])
                                
                                # Send the new response as a new multipart message
                                primary_message, new_message_group = await self._send_long_message(
                                    reaction.message.channel, 
                                    formatted_response,
                                    reference=original_message
                                )
                                
                                # Add reaction to just the primary message
                                await primary_message.add_reaction("🗑️")
                                await primary_message.add_reaction("🔄")  # Mark as already regenerated
                                
                                # Update the context for the new primary message
                                self.message_contexts[primary_message.id] = context
                                
                                # Clean up old context entries
                                for old_id in message_group["message_ids"]:
                                    if old_id in self.message_contexts:
                                        del self.message_contexts[old_id]
                            except (discord.NotFound, discord.HTTPException):
                                # If original message is gone, just send as new message
                                primary_message, new_message_group = await self._send_long_message(
                                    reaction.message.channel, 
                                    formatted_response
                                )
                                await primary_message.add_reaction("🗑️")
                                await primary_message.add_reaction("🔄")
                        else:
                            # Single message - try to edit, fall back to delete and resend
                            try:
                                # First attempt to edit the existing message
                                await reaction.message.edit(content=formatted_response)
                                edited_message = reaction.message
                                
                                # Add a "regenerated" flag reaction to prevent further regeneration
                                await edited_message.add_reaction("🔄")
                                
                            except discord.HTTPException:
                                # If editing fails (e.g., too old message), delete and send new one
                                await reaction.message.delete()
                                
                                # Get the original message
                                try:
                                    original_message = await reaction.message.channel.fetch_message(context["original_message"])
                                    
                                    # Send the new response, potentially splitting if too long
                                    primary_message, new_message_group = await self._send_long_message(
                                        reaction.message.channel, 
                                        formatted_response,
                                        reference=original_message
                                    )
                                    
                                    # Add reactions to new message
                                    await primary_message.add_reaction("🗑️")
                                    await primary_message.add_reaction("🔄")  # Mark as already regenerated
                                    
                                    # Update the context for the new message
                                    self.message_contexts[primary_message.id] = context
                                    
                                    # Clean up old context
                                    if message_id in self.message_contexts:
                                        del self.message_contexts[message_id]
                                except (discord.NotFound, discord.HTTPException):
                                    # Couldn't find original message, just send as a new message
                                    primary_message, new_message_group = await self._send_long_message(
                                        reaction.message.channel, 
                                        formatted_response
                                    )
                                    await primary_message.add_reaction("🗑️")
                        
                        # Update conversation history with the new response
                        channel_history = self._get_channel_conversation(reaction.message.channel.id)
                        
                        # Replace the last bot response or add this one
                        if channel_history and channel_history[-1]["role"] == "assistant":
                            channel_history[-1] = {
                                "role": "assistant",
                                "name": self.character_name,
                                "content": new_response,
                                "timestamp": datetime.datetime.now().isoformat(),
                            }
                        else:
                            channel_history.append({
                                "role": "assistant",
                                "name": self.character_name,
                                "content": new_response,
                                "timestamp": datetime.datetime.now().isoformat(),
                            })
                        
                        # Save the updated conversation
                        self._save_conversation(reaction.message.channel.id, channel_history)
                        
                        # Check if we need to update memory from the regenerated response
                        await self._update_memory_from_conversation(
                            context["user_name"], context["user_message"], new_response
                        )
    async def _generate_temp_tts(self, text):
        """Generate a temporary TTS audio file from text"""
        if (
            not self.ai_client
            or not self.tts_model
            or not self.tts_voice
            or not self.use_tts
        ):
            return None

        try:
            # Create a temporary directory if it doesn't exist
            temp_dir = os.path.join(self.data_dir, "temp_audio")
            os.makedirs(temp_dir, exist_ok=True)

            # Generate a filename based on timestamp for uniqueness
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{self.character_name}_{timestamp}.mp3"
            filepath = os.path.join(temp_dir, filename)

            # Call TTS API
            response = await self.ai_client.audio.speech.create(
                model=self.tts_model, voice=self.tts_voice, input=text
            )

            # Save audio to temporary file
            response.stream_to_file(filepath)
            return filepath

        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None
    
    async def _send_long_message(self, channel, content, reference=None, reply=True):
        """
        Splits long messages into multiple chunks and sends them.
        Returns the sent message info including all message IDs for tracking.
        
        Args:
            channel: The channel to send the message to
            content: The message content
            reference: The message to reply to (if any)
            reply: Whether to use reply mention (defaults to True)
        """
        # Discord message limit is 2000 characters
        MAX_LENGTH = 2000
        
        # Object to track all our messages
        message_group = {
            "is_multipart": False,
            "message_ids": [],
            "primary_id": None,  # First message ID
            "content": content    # Store original content for regeneration
        }
        
        # If message is within limits, just send it normally
        if len(content) <= MAX_LENGTH:
            if reference:
                sent_message = await reference.reply(content, mention_author=reply)
            else:
                sent_message = await channel.send(content)
                
            message_group["message_ids"].append(sent_message.id)
            message_group["primary_id"] = sent_message.id
            return sent_message, message_group
        
        # Message needs to be split
        message_group["is_multipart"] = True
        
        # Split message into chunks
        chunks = []
        current_chunk = ""
        
        # Try to split intelligently at paragraph or sentence boundaries
        paragraphs = content.split('\n\n')
        
        for paragraph in paragraphs:
            # If paragraph itself exceeds limit, split by sentences
            if len(paragraph) > MAX_LENGTH:
                sentences = paragraph.replace('. ', '.\n').split('\n')
                for sentence in sentences:
                    # If adding this sentence would exceed limit, start new chunk
                    if len(current_chunk) + len(sentence) + 2 > MAX_LENGTH:
                        chunks.append(current_chunk)
                        current_chunk = sentence + '\n\n'
                    else:
                        current_chunk += sentence + '\n\n'
            else:
                # Check if adding this paragraph would exceed limit
                if len(current_chunk) + len(paragraph) + 2 > MAX_LENGTH:
                    chunks.append(current_chunk)
                    current_chunk = paragraph + '\n\n'
                else:
                    current_chunk += paragraph + '\n\n'
        
        # Add the final chunk if not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        # Send all chunks
        primary_message = None
        all_messages = []
        
        # Mark chunks with continuation indicator
        chunks = [f"{chunk}\n{'(continued...)' if i < len(chunks) - 1 else ''}" for i, chunk in enumerate(chunks)]
        
        for i, chunk in enumerate(chunks):
            # First chunk is a reply to the original message
            if i == 0 and reference:
                sent_message = await reference.reply(chunk, mention_author=reply)
                primary_message = sent_message
            else:
                # Subsequent chunks are regular messages
                sent_message = await channel.send(chunk)
            
            all_messages.append(sent_message)
            message_group["message_ids"].append(sent_message.id)
        
        if primary_message is None and all_messages:
            primary_message = all_messages[0]
        
        message_group["primary_id"] = primary_message.id if primary_message else None
        
        # Store all sent messages in a tracking dictionary
        if not hasattr(self, "multipart_messages"):
            self.multipart_messages = {}
        
        # Associate all sent message IDs with this message group
        for msg_id in message_group["message_ids"]:
            self.multipart_messages[msg_id] = message_group
        
        return primary_message, message_group

    
    
    async def _update_memory_from_conversation(self, user_name, user_message, bot_response):
        """Extract and store important information from conversations as memories with user attribution"""
        if not self.ai_client or not self.chat_model:
            return
            
        try:
            # Create an improved system prompt that gives clearer instructions for memory extraction
            system_prompt = """You are an AI designed to extract meaningful information from conversations that would be valuable to remember for future interactions.

        Instructions:
        1. Analyze the conversation between the user and the AI.
        2. Identify any significant information about the user such as:
        - Personal preferences (likes, dislikes)
        - Background information (job, location, family)
        - Important events (past or planned)
        - Goals or needs they've expressed
        - Problems they're facing

        3. If you find something worth remembering, output a JSON object with a single key-value pair:
        - Key: A short, descriptive topic name (e.g., "User's Job", "Birthday Plans", "Preferred Music")
        - Value: A concise factual statement summarizing what to remember

        4. If nothing significant was shared, return an empty JSON object: {}

        Examples:
        - User saying "I've been learning to play guitar for 3 months now" → {"Music Interest": "User has been learning guitar for 3 months"}
        - User saying "I have an interview tomorrow at 9am" → {"Job Interview": "User has an interview scheduled tomorrow at 9am"}

        Only extract specific, factual information (not vague impressions), and focus on details about the user, not general topics.
        Unless it is when the user explicitly requests something to be remembered. You should remember such things, regardless of how pointless.
        Your output should be ONLY a valid JSON object with no additional text.
        """
            
            # Construct the conversation content to analyze
            conversation_content = f"User {user_name}: {user_message}\nAI: {bot_response}"
            
            # Call API to analyze conversation
            memory_analysis = await self._call_chat_api(
                conversation_content,
                system_prompt=system_prompt
            )
            print(memory_analysis)
            
            # Process the response to extract memory information
            try:
                # Look for JSON in the response (in case there's any non-JSON text)
                import re
                json_match = re.search(r'\{.*\}', memory_analysis, re.DOTALL)
                
                if json_match:
                    memory_json = json_match.group(0)
                    memory_data = json.loads(memory_json)
                    
                    # Update memory with extracted information and user attribution
                    for topic, detail in memory_data.items():
                        if topic and detail:  # Make sure they're not empty
                            # Keep only meaningful memories (more than 3 chars)
                            if len(detail) > 3:
                                # Store memory with user attribution
                                self.long_term_memory[topic] = {
                                    "detail": detail,
                                    "source": user_name,  # Record who provided this information
                                    "timestamp": datetime.datetime.now().isoformat()
                                }
                                logger.info(f"Added memory from {user_name}: {topic}: {detail}")
                    
                    # Save memory if anything was added
                    if memory_data:
                        self._save_memory()
                else:
                    logger.info("No memory-worthy information found in conversation")
                    
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Failed to parse memory response: {memory_analysis}. Error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error updating memory from conversation: {e}")
                

    async def _handle_ooc_command(self, message: discord.Message):
        """Handle out-of-character commands from the owner"""
        clean_content = message.content.replace("//", "").replace("/ooc", "").strip()
        parts = clean_content.split(" ", 1)
        command = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # This is just the memory-related part of the _handle_ooc_command method

        if command == "memory" or command == "wack":
            if args.lower() == "show":
                memory_display = "**Long-term Memory:**\n"
                if not self.long_term_memory:
                    memory_display += "No memories stored yet."
                else:
                    # Sort memories alphabetically by topic for better readability
                    sorted_memories = sorted(self.long_term_memory.items())
                    for topic, memory_data in sorted_memories:
                        detail = memory_data["detail"]
                        source = memory_data["source"]
                        memory_display += f"- **{topic}**: {detail} (from {source})\n"
                await message.reply(memory_display)
            elif args.lower().startswith("search ") and len(parts) > 2:
                # New command to search memories based on keywords
                search_term = parts[2]
                relevant_memories = self._search_memory(search_term)
                
                if relevant_memories:
                    memory_display = f"**Memories matching '{search_term}':**\n"
                    for memory in relevant_memories:
                        await message.reply(memory_display + memory)
                else:
                    await message.reply(f"No memories found matching '{search_term}'")
            elif args.lower().startswith("add "):
                # Add memory manually
                mem_parts = args[4:].split(":", 1)
                if len(mem_parts) == 2:
                    topic, details = mem_parts
                    # Store with the command issuer as source
                    self.long_term_memory[topic.strip()] = {
                        "detail": details.strip(),
                        "source": message.author.display_name,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    self._save_memory()
                    await message.reply(f"Added memory: {topic.strip()} (from {message.author.display_name})")
                else:
                    await message.reply(
                        "Invalid format. Use: //memory add Topic: Details"
                    )
            elif args.lower().startswith("remove "):
                # Remove memory
                topic = args[7:].strip()
                if topic in self.long_term_memory:
                    del self.long_term_memory[topic]
                    self._save_memory()
                    await message.reply(f"Removed memory: {topic}")
                else:
                    await message.reply(f"Memory topic '{topic}' not found.")
            elif args.lower() == "clear" or command == "wack":
                self.long_term_memory = {}
                self._save_memory()
                await message.reply("All memories cleared.")
        elif command == "lore":
            subparts = args.split(" ", 1)
            subcommand = subparts[0].lower() if subparts else ""
            subargs = subparts[1] if len(subparts) > 1 else ""

            if subcommand == "add" and subargs:
                # Add lorebook entry manually
                lore_parts = subargs.split(":", 1)
                if len(lore_parts) == 2:
                    keyword, content = lore_parts
                    self.lorebook_entries.append(
                        {"keyword": keyword.strip(), "content": content.strip()}
                    )
                    self._save_lorebook()
                    await message.reply(
                        f"Added lorebook entry for keyword: {keyword.strip()}"
                    )
                else:
                    await message.reply(
                        "Invalid format. Use: //lore add Keyword: Content"
                    )
            elif subcommand == "list":
                lore_display = "**Lorebook Entries:**\n"
                if not self.lorebook_entries:
                    lore_display += "No entries yet."
                else:
                    for i, entry in enumerate(self.lorebook_entries):
                        lore_display += f"{i+1}. **{entry['keyword']}**: {entry['content'][:50]}...\n"
                await message.reply(lore_display)
            elif subcommand == "remove" and subargs:
                try:
                    index = int(subargs) - 1
                    if 0 <= index < len(self.lorebook_entries):
                        removed = self.lorebook_entries.pop(index)
                        self._save_lorebook()
                        await message.reply(
                            f"Removed lorebook entry for: {removed['keyword']}"
                        )
                    else:
                        await message.reply("Invalid entry number.")
                except ValueError:
                    await message.reply("Please provide a valid entry number.")
            elif subcommand == "clear":
                self.lorebook_entries = []
                self._save_lorebook()
                await message.reply("All lorebook entries cleared.")

        elif command == "activate":
            self.activated_channels.add(message.channel.id)
            self._save_config()
            await message.reply(
                f"{self.character_name} will now respond to all messages in this channel."
            )

        elif command == "deactivate":
            if message.channel.id in self.activated_channels:
                self.activated_channels.remove(message.channel.id)
                self._save_config()
            await message.reply(
                f"{self.character_name} will now only respond when mentioned or called by name."
            )

        elif command == "persona":
            # Show current persona details with additional traits
            persona_display = f"**{self.character_name} Persona:**\n"
            persona_display += f"**Description:** {self.character_description}\n"
            persona_display += f"**Scenario:** {self.character_scenario}\n"
            
            # Add new personality details
            if self.personality_age:
                persona_display += f"**Age:** {self.personality_age}\n"
            if self.personality_traits:
                persona_display += f"**Traits:** {self.personality_traits}\n"
            if self.personality_likes:
                persona_display += f"**Likes:** {self.personality_likes}\n"
            if self.personality_dislikes:
                persona_display += f"**Dislikes:** {self.personality_dislikes}\n"
            if self.personality_tone:
                persona_display += f"**Tone:** {self.personality_tone}\n"
            if self.personality_history:
                history_preview = self.personality_history[:100] + "..." if len(self.personality_history) > 100 else self.personality_history
                persona_display += f"**History:** {history_preview}\n"
            if self.personality_catchphrases:
                persona_display += f"**Catchphrases:** {self.personality_catchphrases}\n"
            
            await message.reply(persona_display)

        elif command == "save":
            # Save all data
            self._save_config()
            self._save_memory()
            self._save_lorebook()
            await message.reply("All data and settings saved!")

        elif command == "help":
            # Show help information
            help_text = "**Out-of-Character Commands:**\n"
            help_text += "- `//memory show` - Display stored memories\n"
            help_text += "- `//memory add Topic: Details` - Add a memory\n"
            help_text += "- `//memory remove Topic` - Remove a memory\n"
            help_text += "- `//memory clear` - Clear all memories\n"
            help_text += "- `//lore add Keyword: Content` - Add a lorebook entry\n"
            help_text += "- `//lore list` - List all lorebook entries\n"
            help_text += "- `//lore remove #` - Remove a lorebook entry by number\n"
            help_text += "- `//lore clear` - Clear all lorebook entries\n"
            help_text += "- `//activate` - Make the bot respond to all messages\n"
            help_text += "- `//deactivate` - Make the bot only respond when called\n"
            help_text += "- `//persona` - Show the current persona details\n"
            help_text += "- `//save` - Save all data and settings\n"
            help_text += "- `//help` - Show this help information\n"
            await message.reply(help_text)

    def _get_channel_conversation(self, channel_id: int) -> List[Dict]:
        """Get conversation history for a specific channel, limited to 8 messages"""
        # Initialize conversation storage if not exists
        if not hasattr(self, "channel_conversations"):
            self.channel_conversations = {}

        if channel_id not in self.channel_conversations:
            self.channel_conversations[channel_id] = []

        # Ensure we only keep the last 8 messages
        if len(self.channel_conversations[channel_id]) > 8:
            # Keep only the most recent 8 messages
            self.channel_conversations[channel_id] = self.channel_conversations[channel_id][-8:]
            
        return self.channel_conversations[channel_id]

    def _get_relevant_lorebook_entries(self, message_content: str) -> List[str]:
        """Get lorebook entries relevant to the current message"""
        relevant_entries = []

        for entry in self.lorebook_entries:
            # Check if keyword is in the message
            if entry["keyword"].lower() in message_content.lower():
                relevant_entries.append(entry["content"])

        return relevant_entries

    async def _generate_response(
        self,
        user_name: str,
        message_content: str,
        conversation_history: List[Dict],
        relevant_lore: List[str] = None,
    ) -> str:
        """
        Generate a response using the AI API if configured, otherwise fall back to simple responses.
        First checks memories for relevant information before making an API call.
        """
        # Check if there are any memories related to the message content
        memory_matches = []
        for topic, detail in self.long_term_memory.items():
            # Check if any word in the topic is in the message content (case insensitive)
            topic_words = topic.lower().split()
            message_lower = message_content.lower()
            
            # Check for topic matches
            if any(word in message_lower for word in topic_words):
                memory_matches.append(f"{topic}: {detail}")
        
        # Ensure we only use up to 8 messages of history
        if len(conversation_history) > 8:
            conversation_history = conversation_history[-8:]
        
        # Prepare list of all relevant information
        relevant_info = []
        if relevant_lore:
            relevant_info.extend(relevant_lore)
        if memory_matches:
            relevant_info.extend(memory_matches)
            logger.info(f"Found {len(memory_matches)} relevant memories for response generation")
        
        # Try to use the API if configured
        if self.ai_client and self.chat_model:
            response = await self._call_chat_api(
                message_content, user_name, conversation_history, relevant_info
            )
            if response:
                return response

        # Fallback to the original simple response logic
        # Build a prompt using character information and history
        prompt = f"""Character: {self.character_name}
            Description: {self.character_description}
            Scenario: {self.character_scenario}

            User: {user_name}
            Message: {message_content}
            """
            
        # Add relevant information (combined lore and memories)
        if relevant_info and len(relevant_info) > 0:
            prompt += "Relevant information:\n"
            for info in relevant_info:
                prompt += f"- {info}\n"

        # Add conversation history context (limiting to available history)
        history_to_use = conversation_history[:-1]  # Exclude current message
        if history_to_use:
            prompt += "\nRecent conversation:\n"
            for entry in history_to_use:
                prompt += f"{entry['name']}: {entry['content']}\n"

        # Detect basic greeting patterns
        greeting_words = ["hello", "hi", "hey", "greetings", "howdy"]
        if any(word in message_content.lower() for word in greeting_words):
            return f"Hello {user_name}! How can I help you today?"

        # Detect questions
        if "?" in message_content:
            return f"That's an interesting question! Let me think about that..."

        # Default response
        return f"I understand you're saying something about '{message_content[:20]}...'. As {self.character_name}, I would respond appropriately based on my personality and our conversation history."
        # Add helper method for voice disconnection

    async def _disconnect_after_audio(self, voice_client):
        """Disconnect from voice channel after audio finishes playing"""
        # Wait a moment to ensure audio is fully played
        await asyncio.sleep(1)

        # Check if still playing
        if voice_client and not voice_client.is_playing():
            await voice_client.disconnect()


# Add the APISettingModal class
class APISettingModal(discord.ui.Modal):
    """Modal for entering API settings"""

    def __init__(self, title: str):
        super().__init__(title=title)
        self.setting_input = discord.ui.TextInput(
            label="Value:",
            placeholder="Enter the setting value",
            max_length=500,
        )
        self.add_item(self.setting_input)


class TextEditModal(discord.ui.Modal):
    """Modal for editing text fields"""

    def __init__(self, title: str, current_text: str):
        super().__init__(title=title)
        self.text_input = discord.ui.TextInput(
            label="Enter new text:",
            style=discord.TextStyle.paragraph,
            default=current_text,
            max_length=2000,
        )
        self.add_item(self.text_input)


class UserIDModal(discord.ui.Modal):
    """Modal for entering a user ID"""

    def __init__(self, title: str):
        super().__init__(title=title)
        self.user_id_input = discord.ui.TextInput(
            label="User ID:",
            placeholder="Enter the user ID (numbers only)",
            max_length=20,
        )
        self.add_item(self.user_id_input)


class LorebookEntryModal(discord.ui.Modal):
    """Modal for adding lorebook entries"""

    def __init__(self, title: str):
        super().__init__(title=title)
        self.keyword_input = discord.ui.TextInput(
            label="Trigger Keyword:",
            placeholder="Enter the keyword that will trigger this lore",
            max_length=100,
        )
        self.content_input = discord.ui.TextInput(
            label="Lore Content:",
            style=discord.TextStyle.paragraph,
            placeholder="Enter the information for this lorebook entry",
            max_length=2000,
        )
        self.add_item(self.keyword_input)
        self.add_item(self.content_input)


class MemoryManagementView(discord.ui.View):
    """View for managing character memory"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(label="Add Memory", style=discord.ButtonStyle.primary)
    async def add_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MemoryEntryModal()

        async def on_submit(modal_interaction):
            topic = modal.topic_input.value
            details = modal.details_input.value
            
            # Store memory with user attribution
            self.bot.long_term_memory[topic] = {
                "detail": details,
                "source": interaction.user.display_name,  # Use the name of the person adding the memory
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            self.bot._save_memory()
            await modal_interaction.response.send_message(
                f"Added memory: {topic} (from {interaction.user.display_name})", ephemeral=True
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Clear All Memory", style=discord.ButtonStyle.danger)
    async def clear_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.long_term_memory = {}
        self.bot._save_memory()
        await interaction.response.send_message("Memory cleared!", ephemeral=True)


class MemoryEntryModal(discord.ui.Modal):
    """Modal for adding memory entries"""

    def __init__(self):
        super().__init__(title="Add Memory Entry")
        self.topic_input = discord.ui.TextInput(
            label="Topic:",
            placeholder="E.g., User Preferences, Recent Events",
            max_length=100,
        )
        self.details_input = discord.ui.TextInput(
            label="Details:",
            style=discord.TextStyle.paragraph,
            placeholder="Enter the details to remember",
            max_length=1000,
        )
        self.add_item(self.topic_input)
        self.add_item(self.details_input)


class LorebookManagementView(discord.ui.View):
    """View for managing lorebook entries"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(label="Add Entry", style=discord.ButtonStyle.primary)
    async def add_entry(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = LorebookEntryModal(title="Add Lorebook Entry")

        async def on_submit(modal_interaction):
            new_entry = {
                "keyword": modal.keyword_input.value,
                "content": modal.content_input.value,
            }
            self.bot.lorebook_entries.append(new_entry)
            self.bot._save_lorebook()
            await modal_interaction.response.send_message(
                f"Added lorebook entry for keyword: {new_entry['keyword']}",
                ephemeral=True,
            )

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Clear All Entries", style=discord.ButtonStyle.danger)
    async def clear_entries(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.bot.lorebook_entries = []
        self.bot._save_lorebook()
        await interaction.response.send_message(
            "All lorebook entries cleared!", ephemeral=True
        )


class SettingsView(discord.ui.View):
    """View for toggling character settings"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(
        label="Toggle Name in Responses", style=discord.ButtonStyle.secondary
    )
    async def toggle_name(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.bot.add_character_name = not self.bot.add_character_name
        self.bot._save_config()
        await interaction.response.send_message(
            f"Character name in responses: {'Enabled' if self.bot.add_character_name else 'Disabled'}",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Toggle Reply to Name", style=discord.ButtonStyle.secondary
    )
    async def toggle_reply_name(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.bot.reply_to_name = not self.bot.reply_to_name
        self.bot._save_config()
        await interaction.response.send_message(
            f"Reply when name is called: {'Enabled' if self.bot.reply_to_name else 'Disabled'}",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Toggle Reply to Mentions", style=discord.ButtonStyle.secondary
    )
    async def toggle_mentions(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.bot.always_reply_mentions = not self.bot.always_reply_mentions
        self.bot._save_config()
        await interaction.response.send_message(
            f"Reply to @mentions: {'Enabled' if self.bot.always_reply_mentions else 'Disabled'}",
            ephemeral=True,
        )


# Main function to run the bot
def run_bot(config_path: str):
    """Run the character bot with the specified configuration file"""
    bot = OpenShape(config_path)

    # Get token from config
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    token = config.get("bot_token", "")
    if not token:
        print("Error: No bot token provided in config file.")
        return

    # Run the bot
    bot.run(token)


# Example configuration structure and usage
example_config = {
    "bot_token": "YOUR_BOT_TOKEN_HERE",
    "owner_id": 123456789012345678,
    "character_name": "Luna",
    "allowed_guilds": [123456789012345678],
    "command_prefix": "!",
    "system_prompt": "You're a helpful assistant named Luna.",
    "character_description": "Luna is a friendly AI assistant who loves helping people.",
    "character_personality": "Cheerful, kind, and always eager to help.",
    "character_scenario": "Luna is in a Discord server answering questions for users.",
    "add_character_name": True,
    "reply_to_name": True,
    "always_reply_mentions": True,
    "use_tts": False,
    "data_dir": "character_data",
    "api_settings": {
        "base_url": "",
        "api_key": "",
        "chat_model": "",
        "tts_model": "",
        "tts_voice": "",
    },
}

if __name__ == "__main__":
    # Check if config file exists
    config_path = "character_config.json"

    if not os.path.exists(config_path):
        # Create a default config file
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(example_config, f, indent=2)
        print(f"Created default config file at {config_path}")
        print("Please edit this file with your bot token and settings.")
    else:
        # Run the bot with the existing config
        run_bot(config_path)
