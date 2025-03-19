import logging
import os
from typing import Optional, Any, Dict, List
import time
import uuid

# Configure logging with more detail
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("openshape.chroma_integration")

# Default path for shared database
DEFAULT_SHARED_DB_PATH = os.path.join(os.getcwd(), "shared_memory")

def setup_memory_system(bot, shared_db_path: str = DEFAULT_SHARED_DB_PATH) -> Optional[Any]:
    """
    Set up ChromaDB memory system for the bot, completely replacing the old memory system.
    
    Args:
        bot: The OpenShape bot instance
        shared_db_path: Path to the shared ChromaDB database
        
    Returns:
        ChromaMemoryManager: The initialized memory manager or None if setup failed
    """
    try:
        # Make sure the bot has a consistent ID for database collections
        if not hasattr(bot, 'bot_id'):
            # Generate from user.id if available or use a UUID
            if hasattr(bot, 'user') and hasattr(bot.user, 'id'):
                bot.bot_id = f"bot_{bot.user.id}"
            else:
                # For initialization before the bot is fully logged in
                bot.bot_id = f"bot_{uuid.uuid4()}"
            
            logger.info(f"Assigned bot ID: {bot.bot_id}")
        
        # Import here to delay until needed (allows recovery if import fails)
        from .vector_memory import ChromaMemoryManager
        
        # Initialize memory manager with shared database path
        memory_manager = ChromaMemoryManager(bot, shared_db_path)
        logger.info(f"Initialized ChromaDB memory manager for {bot.character_name}")
        
        # Replace memory-related methods on the bot object
        bot.add_memory = memory_manager.add_memory
        bot.remove_memory = memory_manager.remove_memory
        bot.clear_memories = memory_manager.clear_memories
        bot.search_memory = memory_manager.search_memory
        bot.extract_memories_from_text = memory_manager.extract_memories_from_text
        bot.update_memory_from_conversation = memory_manager.update_memory_from_conversation
        bot.format_memories_for_display = memory_manager.format_memories_for_display
        bot.update_memory = memory_manager.update_memory 
        
        # Store direct reference to the memory manager
        bot.memory_manager = memory_manager
        
        # For backwards compatibility only, not actually used anymore
        bot.long_term_memory = {}
        
        return memory_manager
        
    except Exception as e:
        logger.error(f"Failed to set up ChromaDB memory system: {e}")
        
        # Create fallback memory methods
        def fallback_search(*args, **kwargs):
            logger.warning("Using fallback memory search because ChromaDB setup failed")
            return []
            
        def fallback_add(*args, **kwargs):
            logger.warning("Using fallback memory add because ChromaDB setup failed")
            return False
            
        def fallback_remove(*args, **kwargs):
            logger.warning("Using fallback memory remove because ChromaDB setup failed")
            return False
            
        def fallback_clear(*args, **kwargs):
            logger.warning("Using fallback memory clear because ChromaDB setup failed")
            return None
            
        async def fallback_extract(*args, **kwargs):
            logger.warning("Using fallback memory extract because ChromaDB setup failed")
            return 0
            
        async def fallback_update(*args, **kwargs):
            logger.warning("Using fallback memory update because ChromaDB setup failed")
            return None
            
        def fallback_format(*args, **kwargs):
            return "**Memory System Error**\nCould not initialize ChromaDB memory system."
        
        # Assign fallback methods
        bot.add_memory = fallback_add
        bot.remove_memory = fallback_remove
        bot.clear_memories = fallback_clear
        bot.search_memory = fallback_search
        bot.extract_memories_from_text = fallback_extract
        bot.update_memory_from_conversation = fallback_update
        bot.format_memories_for_display = fallback_format
        
        # Create a simple dictionary-based memory for fallback
        bot.long_term_memory = {}
        
        # Return None to indicate failure
        return None


class MemoryCommand:
    """Handles the memory command functionality"""
    
    @staticmethod
    async def execute(bot, interaction):
        """Execute the memory command with ChromaDB integration"""
        try:

            # Import necessary Discord UI classes
            import discord
            
            # Define the pagination view class
            class PaginationView(discord.ui.View):
                def __init__(self, chunks):
                    super().__init__(timeout=180)  # 3 minute timeout
                    self.chunks = chunks
                    self.current_page = 0
                    
                    # Set initial button states
                    self.update_button_states()
                    
                def update_button_states(self):
                    # Disable previous button on first page
                    self.children[0].disabled = (self.current_page == 0)
                    # Disable next button on last page
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

            # Only allow the owner to manage memories
            if interaction.user.id != bot.owner_id:
                memory_display = bot.format_memories_for_display()
                
                # If content fits in one message, send it directly
                if len(memory_display) <= 2000:
                    await interaction.response.send_message(memory_display, ephemeral=True)
                else:
                    await interaction.response.defer(ephemeral=True)
                    
                    # Split memory display into chunks of 1900 characters
                    chunks = [memory_display[i:i+1900] for i in range(0, len(memory_display), 1900)]
                    
                    # Create pagination view and send first page
                    view = PaginationView(chunks)
                    await interaction.followup.send(
                        f"{chunks[0]}\n\n(Page 1/{len(chunks)})", 
                        view=view, 
                        ephemeral=True
                    )
                
                return
            class MemoryManagementView(discord.ui.View):
                def __init__(self, bot_instance):
                    super().__init__()
                    self.bot = bot_instance
                    
                @discord.ui.button(label="Add Memory", style=discord.ButtonStyle.primary)
                async def add_memory(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    # Create modal for adding memory
                    modal = MemoryAddModal(self.bot)
                    await button_interaction.response.send_modal(modal)
                
                @discord.ui.button(label="Edit Memory", style=discord.ButtonStyle.secondary)
                async def edit_memory(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    # First, get all memories to display in a select menu
                    try:
                        results = self.bot.memory_manager.collection.get()
                        
                        if not results or not results['metadatas'] or len(results['metadatas']) == 0:
                            await button_interaction.response.send_message("No memories available to edit.", ephemeral=True)
                            return
                            
                        # Create modal for selecting which memory to edit
                        modal = MemorySelectModal(self.bot, results)
                        await button_interaction.response.send_modal(modal)
                        
                    except Exception as e:
                        logger.error(f"Error fetching memories for edit: {e}")
                        await button_interaction.response.send_message("Failed to retrieve memories for editing.", ephemeral=True)
            
                @discord.ui.button(label="Clear All Memory", style=discord.ButtonStyle.danger)
                async def clear_memory(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    # Create confirm view
                    confirm_view = discord.ui.View()
                    
                    confirm_button = discord.ui.Button(label="Yes, Clear All Memories", style=discord.ButtonStyle.danger)
                    cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
                    
                    async def confirm_callback(confirm_interaction):
                        self.bot.clear_memories()
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
            
            class MemoryAddModal(discord.ui.Modal):
                def __init__(self, bot_instance):
                    super().__init__(title="Add Memory Entry")
                    self.bot = bot_instance
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
                    # First, defer the response since ChromaDB operations might take time
                    await modal_interaction.response.defer(ephemeral=True)
                    
                    topic = self.topic_input.value
                    details = self.details_input.value
                    source = interaction.user.display_name
                    
                    # Add memory
                    success = self.bot.add_memory(topic, details, source)
                    
                    try:
                        if success:
                            # Use followup instead of response.send_message since we've deferred
                            await modal_interaction.followup.send(
                                f"Added memory: {topic} (from {source})", ephemeral=True
                            )
                        else:
                            await modal_interaction.followup.send(
                                "Failed to add memory. Check console for errors.", ephemeral=True
                            )
                    except Exception as e:
                        # This might happen if the followup also times out
                        import logging
                        logger = logging.getLogger("openshape.chroma_integration")
                        logger.error(f"Error responding to interaction: {e}")
                        # No need to re-raise, the memory was still added successfully
            
            class MemorySelectModal(discord.ui.Modal):
                def __init__(self, bot_instance, memory_results):
                    super().__init__(title="Select Memory to Edit")
                    self.bot = bot_instance
                    self.memories = []
                    
                    # Process memory results
                    for i, metadata in enumerate(memory_results['metadatas']):
                        topic = metadata.get('topic', 'Unknown Topic')
                        detail = metadata.get('detail', '')
                        self.memories.append((topic, detail))
                    
                    # Create a select menu of topics
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
                        # Parse the selected memory number
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
                            
                        # Get the selected memory
                        selected_topic, selected_detail = self.memories[selection]
                        
                        # Instead of sending a modal directly, send a message with a button
                        # that will then show the edit modal when clicked
                        view = discord.ui.View()
                        edit_button = discord.ui.Button(label=f"Edit: {selected_topic}", style=discord.ButtonStyle.primary)
                        
                        async def edit_button_callback(button_interaction):
                            edit_modal = MemoryEditModal(self.bot, selected_topic, selected_detail)
                            await button_interaction.response.send_modal(edit_modal)
                            
                        edit_button.callback = edit_button_callback
                        view.add_item(edit_button)
                        
                        await modal_interaction.response.send_message(
                            f"Selected memory: **{selected_topic}**\n\nClick the button below to edit this memory.", 
                            view=view,
                            ephemeral=True
                        )
                        
                    except Exception as e:
                        # Import logger here to avoid the scope issue
                        import logging
                        logger = logging.getLogger("openshape.chroma_integration")
                        logger.error(f"Error in memory selection: {e}")
                        await modal_interaction.response.send_message(
                            "An error occurred while selecting the memory.",
                            ephemeral=True
                        )

            class MemoryEditModal(discord.ui.Modal):
                def __init__(self, bot_instance, topic, detail):
                    super().__init__(title="Edit Memory")
                    self.bot = bot_instance
                    self.original_topic = topic
                    
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
                    # First, defer the response since ChromaDB operations might take time
                    await modal_interaction.response.defer(ephemeral=True)
                    
                    new_topic = self.topic_input.value
                    new_detail = self.details_input.value
                    source = modal_interaction.user.display_name
                    
                    # Handle topic change - if topic changed, we need to remove old and add new
                    if new_topic != self.original_topic:
                        # Remove old memory
                        removed = self.bot.remove_memory(self.original_topic)
                        # Add as new memory
                        success = self.bot.add_memory(new_topic, new_detail, source)
                        
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
                        # Just update the detail
                        if hasattr(self.bot, 'update_memory'):
                            success = self.bot.update_memory(new_topic, new_detail, source)
                        else:
                            # Fallback if update_memory isn't available
                            removed = self.bot.remove_memory(self.original_topic)
                            success = self.bot.add_memory(new_topic, new_detail, source)
                        
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
                        

            # Display memories with management view for bot owner
            view = MemoryManagementView(bot)
            memory_display = bot.format_memories_for_display()
            
            if len(memory_display) <= 2000:
                await interaction.response.send_message(memory_display, view=view, ephemeral=True)
            else:
                # Use pagination for larger content
                await interaction.response.defer(ephemeral=True)
                
                # Split memory display into chunks of 1900 characters
                chunks = [memory_display[i:i+1900] for i in range(0, len(memory_display), 1900)]
                
                # Create combined view with pagination and memory management
                class CombinedView(PaginationView):
                    def __init__(self, chunks, bot_instance):
                        super().__init__(chunks)
                        self.bot = bot_instance
                        
                        # Add memory management buttons
                        add_button = discord.ui.Button(label="Add Memory", style=discord.ButtonStyle.primary, row=1)
                        edit_button = discord.ui.Button(label="Edit Memory", style=discord.ButtonStyle.secondary, row=1)
                        clear_button = discord.ui.Button(label="Clear All Memory", style=discord.ButtonStyle.danger, row=1)
                        
                        # Callbacks for the management buttons
                        async def add_callback(button_interaction):
                            modal = MemoryAddModal(self.bot)
                            await button_interaction.response.send_modal(modal)
                            
                        async def edit_callback(button_interaction):
                            try:
                                results = self.bot.memory_manager.collection.get()
                                
                                if not results or not results['metadatas'] or len(results['metadatas']) == 0:
                                    await button_interaction.response.send_message("No memories available to edit.", ephemeral=True)
                                    return
                                    
                                modal = MemorySelectModal(self.bot, results)
                                await button_interaction.response.send_modal(modal)
                                
                            except Exception as e:
                                logger.error(f"Error fetching memories for edit: {e}")
                                await button_interaction.response.send_message("Failed to retrieve memories for editing.", ephemeral=True)
                        
                        async def clear_callback(button_interaction):
                            confirm_view = discord.ui.View()
                            
                            confirm_button = discord.ui.Button(label="Yes, Clear All Memories", style=discord.ButtonStyle.danger)
                            cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
                            
                            async def confirm_cb(confirm_interaction):
                                self.bot.clear_memories()
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
                
                # Create combined view and send first page
                combined_view = CombinedView(chunks, bot)
                await interaction.followup.send(
                    f"{chunks[0]}\n\n(Page 1/{len(chunks)})",
                    view=combined_view,
                    ephemeral=True
                )
                
        except Exception as e:
            import logging
            logger = logging.getLogger("openshape.chroma_integration")
            logger.error(f"Error in memory command: {e}")
            
            # Try to respond to the interaction if possible
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred while accessing the memory system. Check logs for details.",
                        ephemeral=True
                    )
            except:
                pass  # If this also fails, just log and continue

class SleepCommand:
    """Handles the sleep command functionality"""
    
    @staticmethod
    async def execute(bot, interaction):
        """Execute the sleep command to extract memories from recent conversations"""
        if interaction.user.id != bot.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command", ephemeral=True
            )
            return
        
        # Always defer first to prevent interaction timeouts
        await interaction.response.defer(thinking=True)
        
        try:
            await interaction.followup.send(f"{bot.character_name} is analyzing recent conversations and going to sleep...")
        
            # Fetch recent messages from the channel (up to 30)
            recent_messages = []
            async for message in interaction.channel.history(limit=30):
                # Skip system messages and bot's own messages that aren't the current bot
                if message.author.bot and message.author.id != bot.user.id:
                    continue
                
                # Add message to our list
                recent_messages.append({
                    "author": message.author.display_name,
                    "content": message.content,
                    "id": message.id,
                    "timestamp": message.created_at.isoformat()
                })
            
            if not recent_messages:
                await interaction.followup.send("No recent messages found to analyze.")
                return
                
            # Sort messages by timestamp (oldest first)
            recent_messages.sort(key=lambda m: m["timestamp"])
            
            # Group messages by author over short time spans
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
                if all(msg["author"] == bot.character_name for msg in batch):
                    continue
                
                # Construct a conversation to analyze
                conversation_content = ""
                for msg in batch:
                    conversation_content += f"{msg['author']}: {msg['content']}\n"
                
                # Check if this conversation has substance
                if len(conversation_content.split()) < 10:
                    continue
                
                try:
                    # Extract memories from this conversation batch
                    created = await bot.extract_memories_from_text(conversation_content)
                    memories_created += created
                except Exception as batch_error:
                    import logging
                    logger = logging.getLogger("openshape.chroma_integration")
                    logger.error(f"Error processing conversation batch: {batch_error}")
                    # Continue to next batch rather than failing entirely
                
                # Add a small delay to avoid rate limits
                import asyncio
                await asyncio.sleep(0.5)
            
            # Send a summary of what happened
            if memories_created > 0:
                response = f"{bot.character_name} has processed the recent conversations and created {memories_created} new memories!"
            else:
                response = f"{bot.character_name} analyzed the conversations but didn't find any significant information to remember."
                
            await interaction.followup.send(response)
            
        except Exception as e:
            import logging
            logger = logging.getLogger("openshape.chroma_integration")
            logger.error(f"Error during sleep command: {e}")
            
            try:
                await interaction.followup.send(f"Something went wrong while processing recent messages: {str(e)[:100]}...")
            except:
                # If interaction is already timed out, try sending a direct message
                try:
                    await interaction.channel.send(f"Error during sleep command: {str(e)[:100]}...")
                except:
                    pass  # At this point, just log the error and continue