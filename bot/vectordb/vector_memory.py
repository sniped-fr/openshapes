import chromadb
import os
import json
import logging
import datetime
import uuid
import re
import time
from typing import List

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("openshape.vector_memory")

MAX_MEMORIES_PER_SERVER = 100

class SharedChromaManager:
    _instance = None
    _client = None
    
    @classmethod
    def get_instance(cls, db_path: str = "shared_memory"):
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance
    
    def __init__(self, db_path: str):
        if SharedChromaManager._client is not None:
            self.client = SharedChromaManager._client
            return
            
        os.makedirs(db_path, exist_ok=True)
        
        try:
            self.client = chromadb.PersistentClient(path=db_path)
            SharedChromaManager._client = self.client
            logger.info(f"Initialized shared ChromaDB client at {db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
    
    def get_collection_for_bot(self, collection_name: str, display_name: str) -> chromadb.Collection:
        logger.info(f"Attempting to get/create collection {collection_name} for {display_name}")
        
        try:
            collection_names = [coll for coll in self.client.list_collections()]
            
            if collection_name in collection_names:
                collection = self.client.get_collection(name=collection_name)
                count = collection.count()
                logger.info(f"Retrieved existing collection {collection_name} with {count} memories")
                return collection
            else:
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"display_name": display_name}
                )
                time.sleep(0.5)
                logger.info(f"Created new collection {collection_name}")
                return collection
                
        except Exception as e:
            logger.error(f"Error getting/creating collection: {e}")
            try:
                collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"display_name": display_name}
                )
                count = collection.count()
                logger.info(f"Retrieved/created collection {collection_name} with {count} memories")
                return collection
            except Exception as nested_e:
                logger.error(f"Second attempt failed: {nested_e}")
                raise

class ChromaMemoryManager:
    def __init__(self, bot, shared_db_path: str = "shared_memory"):
        self.bot = bot
        self.guild_collections = {}
        
        if hasattr(bot, 'data_dir') and not os.path.exists(bot.data_dir):
            os.makedirs(bot.data_dir, exist_ok=True)
        
        stable_bot_id = None
        bot_id_file = os.path.join(bot.data_dir, "bot_id.txt") if hasattr(bot, 'data_dir') else None
        
        if bot_id_file and os.path.exists(bot_id_file):
            try:
                with open(bot_id_file, 'r') as f:
                    stable_bot_id = f.read().strip()
                    logger.info(f"Loaded existing bot ID from file: {stable_bot_id}")
            except Exception as e:
                logger.error(f"Error loading bot ID from file: {e}")
        
        if not stable_bot_id and hasattr(bot, 'character_name'):
            import hashlib
            name_hash = hashlib.md5(bot.character_name.encode()).hexdigest()[:12]
            stable_bot_id = f"bot_{name_hash}"
            logger.info(f"Generated stable bot ID from character name: {stable_bot_id}")
            
            if bot_id_file:
                try:
                    with open(bot_id_file, 'w') as f:
                        f.write(stable_bot_id)
                        logger.info(f"Saved stable bot ID to {bot_id_file}")
                except Exception as e:
                    logger.error(f"Error saving bot ID: {e}")
        
        if not stable_bot_id:
            if hasattr(bot, 'user') and bot.user is not None and hasattr(bot.user, 'id'):
                stable_bot_id = f"bot_{bot.user.id}"
                logger.info(f"Using Discord bot ID: {stable_bot_id}")
            else:
                stable_bot_id = f"bot_{uuid.uuid4()}"
                logger.info(f"Generated new bot ID: {stable_bot_id}")
                
                if bot_id_file:
                    try:
                        with open(bot_id_file, 'w') as f:
                            f.write(stable_bot_id)
                            logger.info(f"Saved new bot ID to {bot_id_file}")
                    except Exception as e:
                        logger.error(f"Error saving bot ID: {e}")
        
        bot.bot_id = stable_bot_id
        logger.info(f"Initializing ChromaMemoryManager for {bot.character_name} with stable ID {bot.bot_id}")
        
        self.chroma_manager = SharedChromaManager.get_instance(shared_db_path)
        
        collection_name = bot.bot_id.replace('-', '_')
        try:
            self.collection = self.chroma_manager.get_collection_for_bot(
                collection_name,
                bot.character_name
            )
            logger.info(f"Successfully connected to global collection with {self.collection.count()} memories")
        except Exception as e:
            logger.error(f"Failed to get/create global collection: {e}")
            raise
        
        self.memory_path = os.path.join(bot.data_dir, "memory.json") if hasattr(bot, 'data_dir') else None
        
        if self.memory_path and os.path.exists(self.memory_path):
            self._migrate_legacy_memories()
    
    def get_collection_for_guild(self, guild_id: str) -> chromadb.Collection:
        if guild_id == "global":
            return self.collection
            
        if guild_id in self.guild_collections:
            return self.guild_collections[guild_id]
            
        collection_name = f"{self.bot.bot_id}_guild_{guild_id}".replace('-', '_')
        display_name = f"{self.bot.character_name} (Guild: {guild_id})"
        
        try:
            collection = self.chroma_manager.get_collection_for_bot(
                collection_name,
                display_name
            )
            
            self.guild_collections[guild_id] = collection
            logger.info(f"Created/retrieved collection for guild {guild_id} with {collection.count()} memories")
            return collection
        except Exception as e:
            logger.error(f"Error accessing collection for guild {guild_id}: {e}")
            return self.collection

    def _enforce_memory_limit(self, collection, guild_id: str):
        try:
            count = collection.count()
            
            if count <= MAX_MEMORIES_PER_SERVER:
                return
            
            results = collection.get()
            
            if not results or not results['metadatas'] or len(results['metadatas']) == 0:
                return
                
            memories_with_time = []
            for i, metadata in enumerate(results['metadatas']):
                memory_id = results['ids'][i]
                timestamp = metadata.get('timestamp', '1970-01-01T00:00:00')
                
                try:
                    dt = datetime.datetime.fromisoformat(timestamp)
                    timestamp_value = dt.timestamp()
                except (ValueError, TypeError):
                    timestamp_value = 0
                    
                memories_with_time.append((memory_id, timestamp_value))
            
            memories_with_time.sort(key=lambda x: x[1])
            
            to_remove = count - MAX_MEMORIES_PER_SERVER
            if to_remove <= 0:
                return
                
            ids_to_remove = [m[0] for m in memories_with_time[:to_remove]]
            
            collection.delete(ids=ids_to_remove)
            
            logger.info(f"Removed {len(ids_to_remove)} oldest memories from guild {guild_id} to maintain limit of {MAX_MEMORIES_PER_SERVER}")
            
        except Exception as e:
            logger.error(f"Error enforcing memory limit: {e}")
            
    def _migrate_legacy_memories(self):
        try:
            if self.collection.count() > 0:
                logger.info(f"Collection already has {self.collection.count()} memories, skipping migration")
                return
                
            with open(self.memory_path, "r", encoding="utf-8") as f:
                try:
                    legacy_memory = json.load(f)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in memory file, skipping migration")
                    return
            
            if not legacy_memory:
                logger.info("No legacy memories to migrate")
                return
                
            logger.info(f"Migrating {len(legacy_memory)} memories to ChromaDB global collection")
            
            documents = []
            metadatas = []
            ids = []
            
            for topic, memory_data in legacy_memory.items():
                if isinstance(memory_data, dict) and "detail" in memory_data:
                    document = f"{topic}: {memory_data['detail']}"
                    metadata = {
                        "topic": topic,
                        "detail": memory_data["detail"],
                        "source": memory_data.get("source", "Unknown"),
                        "timestamp": memory_data.get("timestamp", datetime.datetime.now().isoformat()),
                        "guild_id": "global"
                    }
                else:
                    document = f"{topic}: {memory_data}"
                    metadata = {
                        "topic": topic,
                        "detail": str(memory_data),
                        "source": "Unknown",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "guild_id": "global"
                    }
                
                memory_id = str(uuid.uuid4())
                documents.append(document)
                metadatas.append(metadata)
                ids.append(memory_id)
            
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
                        logger.info(f"Added batch of {len(batch_docs)} memories to global ChromaDB collection")
                    except Exception as e:
                        logger.error(f"Error adding memory batch: {e}")
            
            backup_path = f"{self.memory_path}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            os.rename(self.memory_path, backup_path)
            logger.info(f"Successfully migrated {len(documents)} memories and backed up legacy file to {backup_path}")
            
        except Exception as e:
            logger.error(f"Error migrating legacy memories: {e}")
            
    def add_memory(self, topic: str, detail: str, source: str, guild_id: str = "global") -> bool:
        try:
            collection = self.get_collection_for_guild(guild_id)
            
            self._enforce_memory_limit(collection, guild_id)
            
            document = f"{topic}: {detail}"
            
            metadata = {
                "topic": topic,
                "detail": detail,
                "source": source,
                "guild_id": guild_id,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            memory_id = str(uuid.uuid4())
            
            collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[memory_id]
            )
            
            logger.info(f"Added memory for guild {guild_id} from {source}: {topic}: {detail}")
            return True
        except Exception as e:
            logger.error(f"Error adding memory to ChromaDB: {e}")
            return False
        
    def update_memory(self, topic: str, new_detail: str, source: str, guild_id: str = "global") -> bool:
        try:
            collection = self.get_collection_for_guild(guild_id)
            
            results = collection.get(
                where={"topic": topic}
            )
            
            if results and results['ids'] and len(results['ids']) > 0:
                memory_id = results['ids'][0]
                
                document = f"{topic}: {new_detail}"
                
                metadata = {
                    "topic": topic,
                    "detail": new_detail,
                    "source": source,
                    "guild_id": guild_id,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
                collection.update(
                    ids=[memory_id],
                    documents=[document],
                    metadatas=[metadata]
                )
                
                logger.info(f"Updated memory for guild {guild_id}: {topic}: {new_detail}")
                return True
            else:
                logger.info(f"No memory found with topic: {topic} in guild {guild_id}")
                return False
        except Exception as e:
            logger.error(f"Error updating memory: {e}")
            return False
            
    def remove_memory(self, topic: str, guild_id: str = "global") -> bool:
        try:
            collection = self.get_collection_for_guild(guild_id)
            
            results = collection.get(
                where={"topic": topic}
            )
            
            if results and results['ids'] and len(results['ids']) > 0:
                collection.delete(
                    ids=results['ids']
                )
                logger.info(f"Removed memory with topic: {topic} from guild {guild_id}")
                return True
            else:
                logger.info(f"No memory found with topic: {topic} in guild {guild_id}")
                return False
        except Exception as e:
            logger.error(f"Error removing memory: {e}")
            return False
            
    def clear_memories(self, guild_id: str = "global") -> None:
        try:
            collection = self.get_collection_for_guild(guild_id)
            
            results = collection.get()
            
            if results and results['ids'] and len(results['ids']) > 0:
                collection.delete(
                    ids=results['ids']
                )
                logger.info(f"Cleared all memories ({len(results['ids'])} entries) for {self.bot.character_name} in guild {guild_id}")
            else:
                logger.info(f"No memories to clear for {self.bot.character_name} in guild {guild_id}")
                
        except Exception as e:
            logger.error(f"Error clearing memories: {e}")
            
    def search_memory(self, query: str, guild_id: str = "global", limit: int = 5) -> List[str]:
        if not query or len(query.strip()) < 3:
            return []
            
        try:
            collection = self.get_collection_for_guild(guild_id)
            
            logger.info(f"Searching for memories related to: {query} in guild {guild_id}")
            results = collection.query(
                query_texts=[query],
                n_results=min(limit, 10)
            )
            
            memory_matches = []
            
            if results and results['metadatas'] and len(results['metadatas']) > 0 and len(results['metadatas'][0]) > 0:
                for metadata in results['metadatas'][0]:
                    topic = metadata.get('topic', 'Unknown Topic')
                    detail = metadata.get('detail', '')
                    source = metadata.get('source', 'Unknown')
                    
                    formatted_memory = f"{topic}: {detail} (from {source})"
                    memory_matches.append(formatted_memory)
                    
            if memory_matches:
                topics = [m.split(':')[0] for m in memory_matches]
                logger.info(f"Found {len(memory_matches)} relevant memories for '{query}' in guild {guild_id}: {topics}")
                
            return memory_matches
            
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            return []
            
    async def extract_memories_from_text(self, text_content: str, guild_id: str = "global") -> int:
        if not hasattr(self.bot, 'api_integration') or not self.bot.api_integration.client or not self.bot.api_integration.chat_model:
            logger.warning("AI client or chat model not available for memory extraction")
            return 0
        
        try:
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
            
            if not hasattr(self.bot, '_call_chat_api'):
                logger.error("Bot doesn't have _call_chat_api method")
                return 0
                
            memory_analysis = await self.bot._call_chat_api(
                text_content,
                system_prompt=system_prompt
            )
            
            try:
                json_match = re.search(r'\[.*\]', memory_analysis, re.DOTALL)
                
                if json_match:
                    memory_json = json_match.group(0)
                    memory_data = json.loads(memory_json)
                    
                    memories_created = 0
                    
                    for memory in memory_data:
                        topic = memory.get("topic")
                        detail = memory.get("detail")
                        importance = memory.get("importance", 5)
                        
                        if topic and detail and importance >= 3:
                            success = self.add_memory(topic, detail, "Sleep Analysis", guild_id)
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
            
    async def update_memory_from_conversation(self, user_name: str, user_message: str, bot_response: str, guild_id: str = "global") -> None:
        if not hasattr(self.bot, 'api_integration') or not self.bot.api_integration.client or not self.bot.api_integration.chat_model:
            logger.warning("AI client or chat model not available for memory update")
            return
            
        try:
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
            
            conversation_content = f"User {user_name}: {user_message}\nAI: {bot_response}"
            
            if not hasattr(self.bot, '_call_chat_api'):
                logger.error("Bot doesn't have _call_chat_api method")
                return
                
            memory_analysis = await self.bot._call_chat_api(
                conversation_content,
                system_prompt=system_prompt
            )
            
            try:
                json_match = re.search(r'\{.*\}', memory_analysis, re.DOTALL)
                
                if json_match:
                    memory_json = json_match.group(0)
                    memory_data = json.loads(memory_json)
                    
                    for topic, detail in memory_data.items():
                        if topic and detail and len(detail) > 3:
                            self.add_memory(topic, detail, user_name, guild_id)
                    
                else:
                    logger.info("No memory-worthy information found in conversation")
                    
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Failed to parse memory response: {memory_analysis}. Error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error updating memory from conversation: {e}")

    def format_memories_for_display(self, guild_id: str = "global") -> str:
        memory_display = f"**Long-term Memory for {self.bot.character_name}**"
        if guild_id != "global":
            memory_display += f" **in this server (max {MAX_MEMORIES_PER_SERVER} memories):**\n"
        else:
            memory_display += ":\n"
        
        try:
            collection = self.get_collection_for_guild(guild_id)
            
            try:
                results = collection.get()
            except Exception as e:
                logger.error(f"Error getting memories from collection: {e}")
                return memory_display + "Error: Could not retrieve memories from database."
            
            if not results or not results['metadatas'] or len(results['metadatas']) == 0:
                memory_display += "No memories stored yet."
                return memory_display
                
            memories = []
            for i, metadata in enumerate(results['metadatas']):
                topic = metadata.get('topic', 'Unknown Topic')
                detail = metadata.get('detail', '')
                source = metadata.get('source', 'Unknown')
                timestamp = metadata.get('timestamp', '')
                
                try:
                    if timestamp:
                        dt = datetime.datetime.fromisoformat(timestamp)
                        timestamp_key = dt.timestamp()
                    else:
                        timestamp_key = 0
                except ValueError:
                    timestamp_key = 0
                
                memories.append((topic, detail, source, timestamp_key))
                
            memories.sort(key=lambda x: (-x[3], x[0]))
            
            memory_display += f"{len(memories)} memories stored. "
            if guild_id != "global" and len(memories) >= MAX_MEMORIES_PER_SERVER:
                memory_display += f"**Limit reached ({MAX_MEMORIES_PER_SERVER})**. Oldest memories will be replaced.\n\n"
            else:
                memory_display += "\n\n"
                
            for topic, detail, source, _ in memories:
                memory_display += f"- **{topic}**: {detail} (from {source})\n"
                
            return memory_display
            
        except Exception as e:
            logger.error(f"Error formatting memories for display: {e}")
            return memory_display + f"Error retrieving memories: {str(e)}"