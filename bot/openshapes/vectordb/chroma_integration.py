import logging
import os
import uuid
import discord
from typing import Optional, Any
try:
    from openshapes.vectordb.vector_memory import ChromaMemoryManager
except ImportError:
    from vectordb.vector_memory import ChromaMemoryManager
    
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("openshape.chroma_integration")

DEFAULT_SHARED_DB_PATH = os.path.join(os.getcwd(), "shared_memory")

class MemorySystem:
    def __init__(self, bot, shared_db_path: str = DEFAULT_SHARED_DB_PATH):
        self.bot = bot
        self.shared_db_path = shared_db_path
        self.setup_bot_id()
        
    def setup_bot_id(self):
        if not hasattr(self.bot, 'bot_id'):
            if hasattr(self.bot, 'user') and hasattr(self.bot.user, 'id'):
                self.bot.bot_id = f"bot_{self.bot.user.id}"
            else:
                self.bot.bot_id = f"bot_{uuid.uuid4()}"
            
            logger.info(f"Assigned bot ID: {self.bot.bot_id}")
    
    def setup(self) -> Optional[Any]:
        try:
            memory_manager = ChromaMemoryManager(self.bot, self.shared_db_path)
            logger.info(f"Initialized ChromaDB memory manager for {self.bot.character_name}")
            
            self.bot.add_memory = memory_manager.add_memory
            self.bot.remove_memory = memory_manager.remove_memory
            self.bot.clear_memories = memory_manager.clear_memories
            self.bot.search_memory = memory_manager.search_memory
            self.bot.extract_memories_from_text = memory_manager.extract_memories_from_text
            self.bot.update_memory_from_conversation = memory_manager.update_memory_from_conversation
            self.bot.format_memories_for_display = memory_manager.format_memories_for_display
            self.bot.update_memory = memory_manager.update_memory
            
            self.bot.memory_manager = memory_manager
            self.bot.long_term_memory = {}
            
            return memory_manager
            
        except Exception as e:
            logger.error(f"Failed to set up ChromaDB memory system: {e}")
            self._setup_fallback_methods()
            return None
        
    def _setup_fallback_methods(self):
        self.bot.add_memory = self._fallback_add
        self.bot.remove_memory = self._fallback_remove
        self.bot.clear_memories = self._fallback_clear
        self.bot.search_memory = self._fallback_search
        self.bot.extract_memories_from_text = self._fallback_extract
        self.bot.update_memory_from_conversation = self._fallback_update
        self.bot.format_memories_for_display = self._fallback_format
        
        self.bot.long_term_memory = {}
        
    def _fallback_search(self, *args, **kwargs):
        logger.warning("Using fallback memory search because ChromaDB setup failed")
        return []
        
    def _fallback_add(self, *args, **kwargs):
        logger.warning("Using fallback memory add because ChromaDB setup failed")
        return False
        
    def _fallback_remove(self, *args, **kwargs):
        logger.warning("Using fallback memory remove because ChromaDB setup failed")
        return False
        
    def _fallback_clear(self, *args, **kwargs):
        logger.warning("Using fallback memory clear because ChromaDB setup failed")
        return None
        
    async def _fallback_extract(self, *args, **kwargs):
        logger.warning("Using fallback memory extract because ChromaDB setup failed")
        return 0
        
    async def _fallback_update(self, *args, **kwargs):
        logger.warning("Using fallback memory update because ChromaDB setup failed")
        return None
        
    def _fallback_format(self, *args, **kwargs):
        return "**Memory System Error**\nCould not initialize ChromaDB memory system."

class PaginationView(discord.ui.View):
    def __init__(self, chunks):
        super().__init__(timeout=180)
        self.chunks = chunks
        self.current_page = 0
        
        self.update_button_states()
        
    def update_button_states(self):
        self.children[0].disabled = (self.current_page == 0)
        self.children[1].disabled = (self.current_page == len(self.chunks) - 1)
        
    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        self.update_button_states()
        
        await button_interaction.response.edit_message(
            content=f"{self.chunks[self.current_page]}\n\n(Page {self.current_page + 1}/{len(self.chunks)})",
            view=self
        )
        
    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.secondary)
    async def next_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(len(self.chunks) - 1, self.current_page + 1)
        self.update_button_states()
        
        await button_interaction.response.edit_message(
            content=f"{self.chunks[self.current_page]}\n\n(Page {self.current_page + 1}/{len(self.chunks)})",
            view=self
        )

class MemoryAddModal(discord.ui.Modal):
    def __init__(self, bot_instance, guild_id):
        super().__init__(title="Add Memory Entry")
        self.bot = bot_instance
        self.guild_id = guild_id
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
    
    async def on_submit(self, modal_interaction):
        await modal_interaction.response.defer(ephemeral=True)
        
        topic = self.topic_input.value
        details = self.details_input.value
        source = modal_interaction.user.display_name
        
        success = self.bot.add_memory(topic, details, source, self.guild_id)
        
        try:
            if success:
                await modal_interaction.followup.send(
                    f"Added memory: {topic} (from {source})", ephemeral=True
                )
            else:
                await modal_interaction.followup.send(
                    "Failed to add memory. Check console for errors.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error responding to interaction: {e}")

class MemoryEditModal(discord.ui.Modal):
    def __init__(self, bot_instance, topic, detail, guild_id):
        super().__init__(title="Edit Memory")
        self.bot = bot_instance
        self.original_topic = topic
        self.guild_id = guild_id
        
        self.topic_input = discord.ui.TextInput(
            label="Topic:",
            default=topic,
            max_length=100
        )
        
        self.details_input = discord.ui.TextInput(
            label="Details:",
            style=discord.TextStyle.paragraph,
            default=detail,
            max_length=1000
        )
        
        self.add_item(self.topic_input)
        self.add_item(self.details_input)
    
    async def on_submit(self, modal_interaction):
        await modal_interaction.response.defer(ephemeral=True)
        
        new_topic = self.topic_input.value
        new_detail = self.details_input.value
        source = modal_interaction.user.display_name
        
        if new_topic != self.original_topic:
            success = self.bot.add_memory(new_topic, new_detail, source, self.guild_id)
            
            if success:
                await modal_interaction.followup.send(
                    f"Updated memory: {self.original_topic} → {new_topic}",
                    ephemeral=True
                )
            else:
                await modal_interaction.followup.send(
                    "Failed to update memory. Check console for errors.",
                    ephemeral=True
                )
        else:
            if hasattr(self.bot, 'update_memory'):
                success = self.bot.update_memory(new_topic, new_detail, source, self.guild_id)
            else:
                success = self.bot.add_memory(new_topic, new_detail, source, self.guild_id)
            
            if success:
                await modal_interaction.followup.send(
                    f"Updated memory: {new_topic}",
                    ephemeral=True
                )
            else:
                await modal_interaction.followup.send(
                    "Failed to update memory. Check console for errors.",
                    ephemeral=True
                )

class MemorySelectModal(discord.ui.Modal):
    def __init__(self, bot_instance, memory_results, guild_id):
        super().__init__(title="Select Memory to Edit")
        self.bot = bot_instance
        self.memories = []
        self.guild_id = guild_id
        
        for i, metadata in enumerate(memory_results['metadatas']):
            topic = metadata.get('topic', 'Unknown Topic')
            detail = metadata.get('detail', '')
            self.memories.append((topic, detail))
        
        topics = [memory[0] for memory in self.memories]
        topic_options = "\n".join([f"{i+1}. {topic}" for i, topic in enumerate(topics)])
        
        self.topic_select = discord.ui.TextInput(
            label=f"Enter number of memory to edit (1-{len(topics)})",
            placeholder="Enter a number",
            max_length=3
        )
        
        self.topic_list = discord.ui.TextInput(
            label="Available memories:",
            style=discord.TextStyle.paragraph,
            default=topic_options,
            required=False
        )
        
        self.add_item(self.topic_list)
        self.add_item(self.topic_select)
    
    async def on_submit(self, modal_interaction):
        try:
            try:
                selection = int(self.topic_select.value) - 1
                if selection < 0 or selection >= len(self.memories):
                    await modal_interaction.response.send_message(
                        f"Invalid selection. Please choose a number between 1 and {len(self.memories)}.",
                        ephemeral=True
                    )
                    return
            except ValueError:
                await modal_interaction.response.send_message(
                    "Please enter a valid number.",
                    ephemeral=True
                )
                return
                
            selected_topic, selected_detail = self.memories[selection]
            
            view = discord.ui.View()
            edit_button = discord.ui.Button(label=f"Edit: {selected_topic}", style=discord.ButtonStyle.primary)
            
            async def edit_button_callback(button_interaction):
                edit_modal = MemoryEditModal(self.bot, selected_topic, selected_detail, self.guild_id)
                await button_interaction.response.send_modal(edit_modal)
                
            edit_button.callback = edit_button_callback
            view.add_item(edit_button)
            
            await modal_interaction.response.send_message(
                f"Selected memory: **{selected_topic}**\n\nClick the button below to edit this memory.", 
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in memory selection: {e}")
            await modal_interaction.response.send_message(
                "An error occurred while selecting the memory.",
                ephemeral=True
            )

class MemoryManagementView(discord.ui.View):
    def __init__(self, bot_instance, guild_id):
        super().__init__()
        self.bot = bot_instance
        self.guild_id = guild_id
        
    @discord.ui.button(label="Add Memory", style=discord.ButtonStyle.primary)
    async def add_memory(self, button_interaction: discord.Interaction, _: discord.ui.Button):
        modal = MemoryAddModal(self.bot, self.guild_id)
        await button_interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Edit Memory", style=discord.ButtonStyle.secondary)
    async def edit_memory(self, button_interaction: discord.Interaction, _: discord.ui.Button):
        try:
            collection = self.bot.memory_manager.get_collection_for_guild(self.guild_id)
            results = collection.get()
            
            if not results or not results['metadatas'] or len(results['metadatas']) == 0:
                await button_interaction.response.send_message("No memories available to edit.", ephemeral=True)
                return
                
            modal = MemorySelectModal(self.bot, results, self.guild_id)
            await button_interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error fetching memories for edit: {e}")
            await button_interaction.response.send_message("Failed to retrieve memories for editing.", ephemeral=True)

    @discord.ui.button(label="Clear All Memory", style=discord.ButtonStyle.danger)
    async def clear_memory(self, button_interaction: discord.Interaction, _: discord.ui.Button):
        confirm_view = discord.ui.View()
        
        confirm_button = discord.ui.Button(label="Yes, Clear All Memories", style=discord.ButtonStyle.danger)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        
        async def confirm_callback(confirm_interaction):
            self.bot.clear_memories(self.guild_id)
            await confirm_interaction.response.send_message("All memories cleared!", ephemeral=True)
            
        async def cancel_callback(cancel_interaction):
            await cancel_interaction.response.send_message("Memory clear canceled", ephemeral=True)
            
        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)
        
        await button_interaction.response.send_message(
            "⚠️ **Warning**: This will delete ALL memories for this character.\nAre you sure?", 
            view=confirm_view, 
            ephemeral=True
        )

class CombinedView(PaginationView):
    def __init__(self, chunks, bot_instance, guild_id):
        super().__init__(chunks)
        self.bot = bot_instance
        self.guild_id = guild_id
        
        add_button = discord.ui.Button(label="Add Memory", style=discord.ButtonStyle.primary, row=1)
        edit_button = discord.ui.Button(label="Edit Memory", style=discord.ButtonStyle.secondary, row=1)
        clear_button = discord.ui.Button(label="Clear All Memory", style=discord.ButtonStyle.danger, row=1)
        
        async def add_callback(button_interaction):
            modal = MemoryAddModal(self.bot, self.guild_id)
            await button_interaction.response.send_modal(modal)
            
        async def edit_callback(button_interaction):
            try:
                collection = self.bot.memory_manager.get_collection_for_guild(self.guild_id)
                results = collection.get()
                
                if not results or not results['metadatas'] or len(results['metadatas']) == 0:
                    await button_interaction.response.send_message("No memories available to edit.", ephemeral=True)
                    return
                    
                modal = MemorySelectModal(self.bot, results, self.guild_id)
                await button_interaction.response.send_modal(modal)
                
            except Exception as e:
                logger.error(f"Error fetching memories for edit: {e}")
                await button_interaction.response.send_message("Failed to retrieve memories for editing.", ephemeral=True)
        
        async def clear_callback(button_interaction):
            confirm_view = discord.ui.View()
            
            confirm_button = discord.ui.Button(label="Yes, Clear All Memories", style=discord.ButtonStyle.danger)
            cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
            
            async def confirm_cb(confirm_interaction):
                self.bot.clear_memories(self.guild_id)
                await confirm_interaction.response.send_message("All memories cleared!", ephemeral=True)
                
            async def cancel_cb(cancel_interaction):
                await cancel_interaction.response.send_message("Memory clear canceled", ephemeral=True)
                
            confirm_button.callback = confirm_cb
            cancel_button.callback = cancel_cb
            
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)
            
            await button_interaction.response.send_message(
                "⚠️ **Warning**: This will delete ALL memories for this character.\nAre you sure?", 
                view=confirm_view, 
                ephemeral=True
            )
        
        add_button.callback = add_callback
        edit_button.callback = edit_callback
        clear_button.callback = clear_callback
        
        self.add_item(add_button)
        self.add_item(edit_button)
        self.add_item(clear_button)

class MemoryCommand:
    @staticmethod
    async def execute(bot, interaction):
        try:
            guild_id = str(interaction.guild.id) if interaction.guild else "global"
            
            if interaction.user.id != bot.config_manager.get("owner_id"):
                return await MemoryCommand._handle_user_view(bot, interaction, guild_id)
            else:
                return await MemoryCommand._handle_owner_view(bot, interaction, guild_id)
                
        except Exception as e:
            logger.error(f"Error in memory command: {e}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred while accessing the memory system. Check logs for details.",
                        ephemeral=True
                    )
            except Exception:
                pass
    
    @staticmethod
    async def _handle_user_view(bot, interaction, guild_id):
        memory_display = bot.format_memories_for_display(guild_id)
        
        if len(memory_display) <= 2000:
            await interaction.response.send_message(memory_display, ephemeral=True)
        else:
            await interaction.response.defer(ephemeral=True)
            
            chunks = [memory_display[i:i+1900] for i in range(0, len(memory_display), 1900)]
            
            view = PaginationView(chunks)
            await interaction.followup.send(
                f"{chunks[0]}\n\n(Page 1/{len(chunks)})", 
                view=view, 
                ephemeral=True
            )
    
    @staticmethod
    async def _handle_owner_view(bot, interaction, guild_id):
        view = MemoryManagementView(bot, guild_id)
        memory_display = bot.format_memories_for_display(guild_id)
        
        if len(memory_display) <= 2000:
            await interaction.response.send_message(memory_display, view=view, ephemeral=True)
        else:
            await interaction.response.defer(ephemeral=True)
            
            chunks = [memory_display[i:i+1900] for i in range(0, len(memory_display), 1900)]
            
            combined_view = CombinedView(chunks, bot, guild_id)
            await interaction.followup.send(
                f"{chunks[0]}\n\n(Page 1/{len(chunks)})",
                view=combined_view,
                ephemeral=True
            )

class ConversationProcessor:
    def __init__(self, bot, channel):
        self.bot = bot
        self.channel = channel
        
    async def extract_recent_memories(self, limit=30):
        recent_messages = []
        async for message in self.channel.history(limit=limit):
            if message.author.bot and message.author.id != self.bot.user.id:
                continue
            
            recent_messages.append({
                "author": message.author.display_name,
                "content": message.content,
                "id": message.id,
                "timestamp": message.created_at.isoformat()
            })
        
        return recent_messages
        
    def batch_messages(self, messages):
        if not messages:
            return []
            
        messages.sort(key=lambda m: m["timestamp"])
        
        batched_conversations = []
        current_batch = []
        last_author = None
        
        for msg in messages:
            if last_author != msg["author"] or len(current_batch) >= 5:
                if current_batch:
                    batched_conversations.append(current_batch)
                current_batch = [msg]
            else:
                current_batch.append(msg)
            
            last_author = msg["author"]
        
        if current_batch:
            batched_conversations.append(current_batch)
            
        return batched_conversations
        
    async def process_conversations(self, batched_conversations, guild_id):
        memories_created = 0
        
        for batch in batched_conversations:
            if all(msg["author"] == self.bot.character_name for msg in batch):
                continue
            
            conversation_content = ""
            for msg in batch:
                conversation_content += f"{msg['author']}: {msg['content']}\n"
            
            if len(conversation_content.split()) < 10:
                continue
            
            try:
                created = await self.bot.extract_memories_from_text(conversation_content, guild_id)
                memories_created += created
            except Exception as batch_error:
                logger.error(f"Error processing conversation batch: {batch_error}")
            
            import asyncio
            await asyncio.sleep(0.5)
            
        return memories_created

class SleepCommand:
    @staticmethod
    async def execute(bot, interaction):
        if interaction.user.id != bot.config_manager.get("owner_id"):
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return
        
        await interaction.response.defer(thinking=True)
        
        guild_id = str(interaction.guild.id) if interaction.guild else "global"
        
        try:
            await interaction.followup.send(f"{bot.character_name} is analyzing recent conversations and going to sleep...")
        
            processor = ConversationProcessor(bot, interaction.channel)
            recent_messages = await processor.extract_recent_memories()
            
            if not recent_messages:
                await interaction.followup.send("No recent messages found to analyze.")
                return
                
            batched_conversations = processor.batch_messages(recent_messages)
            memories_created = await processor.process_conversations(batched_conversations, guild_id)
            
            if memories_created > 0:
                response = f"{bot.character_name} has processed the recent conversations and created {memories_created} new memories!"
            else:
                response = f"{bot.character_name} analyzed the conversations but didn't find any significant information to remember."
                
            await interaction.followup.send(response)
            
        except Exception as e:
            logger.error(f"Error during sleep command: {e}")
            
            try:
                await interaction.followup.send(f"Something went wrong while processing recent messages: {str(e)[:100]}...")
            except Exception:
                try:
                    await interaction.channel.send(f"Error during sleep command: {str(e)[:100]}...")
                except Exception:
                    pass