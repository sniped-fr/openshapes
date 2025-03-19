import chromadb
import os
import json
import logging
import datetime
import uuid
import re
import time
from typing import List, Dict, Optional, Any

# Configure logging with more detail
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("openshape.vector_memory")

class SharedChromaManager:
    """
    Singleton manager for shared ChromaDB instance across multiple bots
    """
    _instance = None
    _client = None
    
    @classmethod
    def get_instance(cls, db_path: str = "shared_memory"):
        """Get or create the shared ChromaDB manager instance"""
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance
    
    def __init__(self, db_path: str):
        """Initialize the shared ChromaDB client"""
        if SharedChromaManager._client is not None:
            # If we already have a client, use it
            self.client = SharedChromaManager._client
            return
            
        # Create database directory if it doesn't exist
        os.makedirs(db_path, exist_ok=True)
        
        # Initialize Chroma client
        try:
            self.client = chromadb.PersistentClient(path=db_path)
            SharedChromaManager._client = self.client
            logger.info(f"Initialized shared ChromaDB client at {db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
    
    def get_collection_for_bot(self, bot_id: str, bot_name: str) -> chromadb.Collection:
        """Get or create a collection for a specific bot"""
        collection_name = bot_id.replace('-', '_')  # Sanitize ID for Chroma
        logger.info(f"Attempting to get/create collection {collection_name} for {bot_name}")
        
        try:
            # In ChromaDB v0.6.0, list_collections() returns collection names directly
            all_collections = self.client.list_collections()
            print(all_collections)
            
            # Check if collection exists directly by name comparison
            collection_exists = collection_name in all_collections
            
            if collection_exists:
                # Collection exists, get it
                collection = self.client.get_collection(name=collection_name)
                count = collection.count()
                logger.info(f"Retrieved existing collection for {bot_name} (ID: {collection_name}) with {count} memories")
                return collection
            else:
                # Collection doesn't exist, create it
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"bot_id": bot_id, "bot_name": bot_name}
                )
                # Small delay to ensure collection is fully created
                time.sleep(0.5)
                logger.info(f"Created new collection for {bot_name} (ID: {collection_name})")
                return collection
                
        except Exception as e:
            logger.error(f"Error getting/creating collection: {e}")
            # Try a different approach for ChromaDB v0.6.0
            try:
                # Direct attempt to get the collection, creates if doesn't exist
                collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"bot_id": bot_id, "bot_name": bot_name}
                )
                count = collection.count()
                logger.info(f"Retrieved/created collection for {bot_name} (ID: {collection_name}) with {count} memories")
                return collection
            except Exception as nested_e:
                logger.error(f"Second attempt failed: {nested_e}")
                raise

class ChromaMemoryManager:
    """Memory manager using ChromaDB with shared instance support"""
    
    def __init__(self, bot, shared_db_path: str = "shared_memory"):
        """Initialize ChromaMemoryManager with bot instance and shared ChromaDB client"""
        self.bot = bot
        
        # Create data directory if it doesn't exist
        if hasattr(bot, 'data_dir') and not os.path.exists(bot.data_dir):
            os.makedirs(bot.data_dir, exist_ok=True)
        
        # Create a stable, consistent bot_id based on character name
        stable_bot_id = None
        bot_id_file = os.path.join(bot.data_dir, "bot_id.txt") if hasattr(bot, 'data_dir') else None
        
        # Try to load existing bot_id from file first
        if bot_id_file and os.path.exists(bot_id_file):
            try:
                with open(bot_id_file, 'r') as f:
                    stable_bot_id = f.read().strip()
                    logger.info(f"Loaded existing bot ID from file: {stable_bot_id}")
            except Exception as e:
                logger.error(f"Error loading bot ID from file: {e}")
        
        # If no ID from file, create a stable one based on character name
        if not stable_bot_id and hasattr(bot, 'character_name'):
            import hashlib
            # Create deterministic ID based on character name
            name_hash = hashlib.md5(bot.character_name.encode()).hexdigest()[:12]
            stable_bot_id = f"bot_{name_hash}"
            logger.info(f"Generated stable bot ID from character name: {stable_bot_id}")
            
            # Save this ID for future use
            if bot_id_file:
                try:
                    with open(bot_id_file, 'w') as f:
                        f.write(stable_bot_id)
                        logger.info(f"Saved stable bot ID to {bot_id_file}")
                except Exception as e:
                    logger.error(f"Error saving bot ID: {e}")
        
        # Fall back to discord ID or UUID if needed
        if not stable_bot_id:
            if hasattr(bot, 'user') and bot.user is not None and hasattr(bot.user, 'id'):
                stable_bot_id = f"bot_{bot.user.id}"
                logger.info(f"Using Discord bot ID: {stable_bot_id}")
            else:
                # Last resort: Generate a UUID, but save it
                stable_bot_id = f"bot_{uuid.uuid4()}"
                logger.info(f"Generated new bot ID: {stable_bot_id}")
                
                # Save this ID for future use
                if bot_id_file:
                    try:
                        with open(bot_id_file, 'w') as f:
                            f.write(stable_bot_id)
                            logger.info(f"Saved new bot ID to {bot_id_file}")
                    except Exception as e:
                        logger.error(f"Error saving bot ID: {e}")
        
        # Set the bot_id on the bot instance
        bot.bot_id = stable_bot_id
        logger.info(f"Initializing ChromaMemoryManager for {bot.character_name} with stable ID {bot.bot_id}")
        
        # Get the shared ChromaDB manager
        self.chroma_manager = SharedChromaManager.get_instance(shared_db_path)
        
        # Get or create a collection for this bot
        try:
            self.collection = self.chroma_manager.get_collection_for_bot(
                bot.bot_id, 
                bot.character_name
            )
            logger.info(f"Successfully connected to collection with {self.collection.count()} memories")
        except Exception as e:
            logger.error(f"Failed to get/create collection: {e}")
            raise
        
        # Legacy memory migration path
        self.memory_path = os.path.join(bot.data_dir, "memory.json") if hasattr(bot, 'data_dir') else None
        
        # Migrate legacy memories if available
        if self.memory_path and os.path.exists(self.memory_path):
            self._migrate_legacy_memories()
            
    def _migrate_legacy_memories(self):
        """Migrate memories from legacy JSON format to ChromaDB"""
        try:
            # Check if migration is needed by looking at collection count
            if self.collection.count() > 0:
                logger.info(f"Collection already has {self.collection.count()} memories, skipping migration")
                return
                
            # Load legacy memories
            with open(self.memory_path, "r", encoding="utf-8") as f:
                try:
                    legacy_memory = json.load(f)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in memory file, skipping migration")
                    return
            
            if not legacy_memory:
                logger.info("No legacy memories to migrate")
                return
                
            logger.info(f"Migrating {len(legacy_memory)} memories to ChromaDB")
            
            # Prepare batches for migration
            documents = []
            metadatas = []
            ids = []
            
            for topic, memory_data in legacy_memory.items():
                if isinstance(memory_data, dict) and "detail" in memory_data:
                    # New format
                    document = f"{topic}: {memory_data['detail']}"
                    metadata = {
                        "topic": topic,
                        "detail": memory_data["detail"],
                        "source": memory_data.get("source", "Unknown"),
                        "timestamp": memory_data.get("timestamp", datetime.datetime.now().isoformat())
                    }
                else:
                    # Old format
                    document = f"{topic}: {memory_data}"
                    metadata = {
                        "topic": topic,
                        "detail": str(memory_data),
                        "source": "Unknown",
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                
                memory_id = str(uuid.uuid4())
                documents.append(document)
                metadatas.append(metadata)
                ids.append(memory_id)
            
            # Add memories in batches
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i+batch_size]
                batch_meta = metadatas[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]
                
                if batch_docs:
                    try:
                        self.collection.add(
                            documents=batch_docs,
                            metadatas=batch_meta,
                            ids=batch_ids
                        )
                        logger.info(f"Added batch of {len(batch_docs)} memories to ChromaDB")
                    except Exception as e:
                        logger.error(f"Error adding memory batch: {e}")
            
            # Backup the old memory file
            backup_path = f"{self.memory_path}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            os.rename(self.memory_path, backup_path)
            logger.info(f"Successfully migrated {len(documents)} memories and backed up legacy file to {backup_path}")
            
        except Exception as e:
            logger.error(f"Error migrating legacy memories: {e}")
            
    def add_memory(self, topic: str, detail: str, source: str) -> bool:
        """Add a memory with attribution to ChromaDB"""
        try:
            # Create a document that combines topic and detail for better semantic search
            document = f"{topic}: {detail}"
            
            # Prepare metadata
            metadata = {
                "topic": topic,
                "detail": detail,
                "source": source,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # Generate a unique ID
            memory_id = str(uuid.uuid4())
            
            # Add to ChromaDB
            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[memory_id]
            )
            
            logger.info(f"Added memory from {source}: {topic}: {detail}")
            return True
        except Exception as e:
            logger.error(f"Error adding memory to ChromaDB: {e}")
            return False
        
    def update_memory(self, topic: str, new_detail: str, source: str) -> bool:
        """Update an existing memory by topic"""
        try:
            # Query for memories with this topic
            results = self.collection.get(
                where={"topic": topic}
            )
            
            if results and results['ids'] and len(results['ids']) > 0:
                # Get the first matching memory (should be unique by topic)
                memory_id = results['ids'][0]
                
                # Create a document that combines topic and detail for better semantic search
                document = f"{topic}: {new_detail}"
                
                # Prepare updated metadata
                metadata = {
                    "topic": topic,
                    "detail": new_detail,
                    "source": source,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
                # Update in ChromaDB
                self.collection.update(
                    ids=[memory_id],
                    documents=[document],
                    metadatas=[metadata]
                )
                
                logger.info(f"Updated memory: {topic}: {new_detail}")
                return True
            else:
                logger.info(f"No memory found with topic: {topic}")
                return False
        except Exception as e:
            logger.error(f"Error updating memory: {e}")
            return False
            
    def remove_memory(self, topic: str) -> bool:
        """Remove memories by topic"""
        try:
            # Query for memories with this topic
            results = self.collection.get(
                where={"topic": topic}
            )
            
            if results and results['ids'] and len(results['ids']) > 0:
                # Delete the found memories
                self.collection.delete(
                    ids=results['ids']
                )
                logger.info(f"Removed memory with topic: {topic}")
                return True
            else:
                logger.info(f"No memory found with topic: {topic}")
                return False
        except Exception as e:
            logger.error(f"Error removing memory: {e}")
            return False
            
    def clear_memories(self) -> None:
        """Clear all memories for this bot"""
        try:
            # Get all memory IDs
            results = self.collection.get()
            
            if results and results['ids'] and len(results['ids']) > 0:
                # Delete all memories
                self.collection.delete(
                    ids=results['ids']
                )
                logger.info(f"Cleared all memories ({len(results['ids'])} entries) for {self.bot.character_name}")
            else:
                logger.info(f"No memories to clear for {self.bot.character_name}")
                
        except Exception as e:
            logger.error(f"Error clearing memories: {e}")
            
    def search_memory(self, query: str, limit: int = 5) -> List[str]:
        """
        Search for memories relevant to the provided query using vector similarity.
        
        Args:
            query: The search query
            limit: Maximum number of results to return
            
        Returns:
            List of relevant memory strings in format "Topic: Detail (from Source)"
        """
        if not query or len(query.strip()) < 3:
            return []
            
        try:
            # Search using query_text for semantic similarity
            print(f"Searching for memories related to: {query}")
            results = self.collection.query(
                query_texts=[query],
                n_results=min(limit, 10)  # Cap at 10 for safety
            )
            
            memory_matches = []
            
            if results and results['metadatas'] and len(results['metadatas']) > 0 and len(results['metadatas'][0]) > 0:
                for metadata in results['metadatas'][0]:
                    # Format the memory string
                    topic = metadata.get('topic', 'Unknown Topic')
                    detail = metadata.get('detail', '')
                    source = metadata.get('source', 'Unknown')
                    
                    formatted_memory = f"{topic}: {detail} (from {source})"
                    memory_matches.append(formatted_memory)
                    
            # Log what we found
            if memory_matches:
                topics = [m.split(':')[0] for m in memory_matches]
                logger.info(f"Found {len(memory_matches)} relevant memories for '{query}': {topics}")
                
            return memory_matches
            
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            return []
            
    async def extract_memories_from_text(self, text_content: str) -> int:
        """Extract and store important information from any text as memories"""
        if not hasattr(self.bot, 'ai_client') or not self.bot.ai_client or not hasattr(self.bot, 'chat_model') or not self.bot.chat_model:
            logger.warning("AI client or chat model not available for memory extraction")
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
            
            # Check that the _call_chat_api method exists
            if not hasattr(self.bot, '_call_chat_api'):
                logger.error("Bot doesn't have _call_chat_api method")
                return 0
                
            # Call API to analyze conversation
            memory_analysis = await self.bot._call_chat_api(
                text_content,
                system_prompt=system_prompt
            )
            
            # Process the response to extract memory information
            try:
                # Look for JSON in the response (in case there's any non-JSON text)
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
                            success = self.add_memory(topic, detail, "Sleep Analysis")
                            if success:
                                memories_created += 1
                    
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
            
    async def update_memory_from_conversation(self, user_name: str, user_message: str, bot_response: str) -> None:
        """Extract and store important information from conversations as memories with user attribution"""
        if not hasattr(self.bot, 'ai_client') or not self.bot.ai_client or not hasattr(self.bot, 'chat_model') or not self.bot.chat_model:
            logger.warning("AI client or chat model not available for memory update")
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
        Instead of "User", use the explicit username associated with the given request. "User" would refer to where you are not certain what someone said. Assign a proper name whenevr you are reasonably able.
        Your output should be ONLY a valid JSON object with no additional text.
        """
            
            # Construct the conversation content to analyze
            conversation_content = f"User {user_name}: {user_message}\nAI: {bot_response}"
            
            # Check that the _call_chat_api method exists
            if not hasattr(self.bot, '_call_chat_api'):
                logger.error("Bot doesn't have _call_chat_api method")
                return
                
            # Call API to analyze conversation
            memory_analysis = await self.bot._call_chat_api(
                conversation_content,
                system_prompt=system_prompt
            )
            
            # Process the response to extract memory information
            try:
                # Look for JSON in the response (in case there's any non-JSON text)
                json_match = re.search(r'\{.*\}', memory_analysis, re.DOTALL)
                
                if json_match:
                    memory_json = json_match.group(0)
                    memory_data = json.loads(memory_json)
                    
                    # Update memory with extracted information and user attribution
                    for topic, detail in memory_data.items():
                        if topic and detail and len(detail) > 3:  # Make sure they're not empty and meaningful
                            self.add_memory(topic, detail, user_name)
                    
                else:
                    logger.info("No memory-worthy information found in conversation")
                    
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Failed to parse memory response: {memory_analysis}. Error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error updating memory from conversation: {e}")

    def format_memories_for_display(self) -> str:
        """Format memories for display in Discord"""
        memory_display = "**Long-term Memory:**\n"
        
        try:
            # Get all memories from ChromaDB
            try:
                results = self.collection.get()
            except Exception as e:
                logger.error(f"Error getting memories from collection: {e}")
                return memory_display + "Error: Could not retrieve memories from database."
            
            if not results or not results['metadatas'] or len(results['metadatas']) == 0:
                memory_display += "No memories stored yet."
                return memory_display
                
            # Sort by topic for better readability
            memories = []
            for i, metadata in enumerate(results['metadatas']):
                topic = metadata.get('topic', 'Unknown Topic')
                detail = metadata.get('detail', '')
                source = metadata.get('source', 'Unknown')
                timestamp = metadata.get('timestamp', '')
                
                # Parse timestamp for sorting if available
                try:
                    if timestamp:
                        dt = datetime.datetime.fromisoformat(timestamp)
                        timestamp_key = dt.timestamp()
                    else:
                        timestamp_key = 0
                except ValueError:
                    timestamp_key = 0
                
                memories.append((topic, detail, source, timestamp_key))
                
            # Sort by recency (newest first) then alphabetically by topic
            memories.sort(key=lambda x: (-x[3], x[0]))
            
            # Format each memory
            for topic, detail, source, _ in memories:
                memory_display += f"- **{topic}**: {detail} (from {source})\n"
                
            return memory_display
            
        except Exception as e:
            logger.error(f"Error formatting memories for display: {e}")
            return memory_display + f"Error retrieving memories: {str(e)}"