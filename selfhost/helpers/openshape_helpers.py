import json
import os
import logging
import datetime
import re
import asyncio
import hashlib
import discord
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logger = logging.getLogger("openshape.helpers")

class MemoryManager:
    """Handles all memory-related operations"""
    def __init__(self, bot):
        self.bot = bot
        self.memory_path = os.path.join(bot.data_dir, "memory.json")
        self.long_term_memory = {}
        self._load_memory()
        
    def _load_memory(self):
        """Load memory from file with updated memory structure"""
        if os.path.exists(self.memory_path):
            with open(self.memory_path, "r", encoding="utf-8") as f:
                loaded_memory = json.load(f)
                
                # Check if we need to migrate old memory format
                if loaded_memory and isinstance(next(iter(loaded_memory.values()), ""), str):
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
            
    def _save_memory(self):
        """Save memory to file"""
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.long_term_memory, f, indent=2)
            
    def add_memory(self, topic: str, detail: str, source: str) -> None:
        """Add a memory with attribution"""
        self.long_term_memory[topic] = {
            "detail": detail,
            "source": source,
            "timestamp": datetime.datetime.now().isoformat()
        }
        logger.info(f"Added memory from {source}: {topic}: {detail}")
        self._save_memory()
        
    def remove_memory(self, topic: str) -> bool:
        """Remove a memory by topic"""
        if topic in self.long_term_memory:
            del self.long_term_memory[topic]
            self._save_memory()
            return True
        return False
        
    def clear_memories(self) -> None:
        """Clear all memories"""
        self.long_term_memory = {}
        self._save_memory()
        
    def search_memory(self, query: str) -> List[str]:
        """
        Search for memories relevant to the provided query.
        Uses more sophisticated matching to find relevant memories.
        
        Args:
            query: The search query
            
        Returns:
            List of relevant memory strings in format "Topic: Detail (from Source)"
        """
        if not self.long_term_memory:
            return []
            
        memory_matches = []
        query_lower = query.lower().split()
        
        # Score each memory for relevance
        memory_scores = {}
        
        for topic, memory_data in self.long_term_memory.items():
            score = 0
            topic_lower = topic.lower()
            detail = memory_data["detail"]
            source = memory_data["source"]
            
            # Direct topic match (highest priority)
            if topic_lower in query.lower():
                score += 10
                
            # Word-level matching
            topic_words = topic_lower.split()
            for word in topic_words:
                if len(word) > 3 and word in query_lower:  # Only match significant words
                    score += 3
                    
            # Look for words from the detail in the query
            detail_words = set(detail.lower().split())
            for word in detail_words:
                if len(word) > 3 and word in query_lower:
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
        
    async def extract_memories_from_text(self, text_content: str) -> int:
        """Extract and store important information from any text as memories"""
        if not self.bot.ai_client or not self.bot.chat_model:
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
                            self.add_memory(topic, detail, "Sleep Analysis")
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
        if not self.bot.ai_client or not self.bot.chat_model:
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
        if not self.long_term_memory:
            memory_display += "No memories stored yet."
        else:
            # Sort memories alphabetically by topic for better readability
            sorted_memories = sorted(self.long_term_memory.items())
            for topic, memory_data in sorted_memories:
                detail = memory_data["detail"]
                source = memory_data["source"]
                memory_display += f"- **{topic}**: {detail} (from {source})\n"
        return memory_display


class TTSHandler:
    """Handles all TTS and audio-related operations"""
    def __init__(self, bot):
        self.bot = bot
        self.audio_dir = os.path.join(bot.data_dir, "audio")
        os.makedirs(self.audio_dir, exist_ok=True)
        # Create temp directory for temporary audio files
        self.temp_dir = os.path.join(bot.data_dir, "temp_audio")
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def _extract_speech_text(self, text: str, ignore_asterisks: bool = False, only_narrate_quotes: bool = False) -> str:
        """Extract text for TTS based on formatting preferences"""
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
        
    async def generate_tts(self, text: str) -> Optional[str]:
        """Generate TTS audio from text and return file path"""
        if (
            not self.bot.ai_client
            or not self.bot.tts_model
            or not self.bot.tts_voice
            or not self.bot.use_tts
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
            text_hash = hashlib.md5(text.encode()).hexdigest()[:10]
            filename = f"{self.bot.character_name}_{text_hash}.mp3"
            filepath = os.path.join(self.audio_dir, filename)

            # Check if file already exists
            if os.path.exists(filepath):
                return filepath

            # Call TTS API
            response = await self.bot.ai_client.audio.speech.create(
                model=self.bot.tts_model, voice=self.bot.tts_voice, input=speech_text
            )

            # Save audio file
            response.stream_to_file(filepath)
            return filepath

        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None
            
    async def generate_temp_tts(self, text: str) -> Optional[str]:
        """Generate a temporary TTS file that will be deleted after use"""
        if (
            not self.bot.ai_client
            or not self.bot.tts_model
            or not self.bot.tts_voice
            or not self.bot.use_tts
        ):
            return None

        try:
            # Clean/prepare the text for TTS
            speech_text = self._extract_speech_text(text, ignore_asterisks=True)
            
            if not speech_text:
                return None
                
            # Generate a filename based on timestamp for uniqueness
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{self.bot.character_name}_{timestamp}.mp3"
            filepath = os.path.join(self.temp_dir, filename)

            # Call TTS API
            response = await self.bot.ai_client.audio.speech.create(
                model=self.bot.tts_model, voice=self.bot.tts_voice, input=speech_text
            )

            # Save audio to temporary file
            response.stream_to_file(filepath)
            return filepath

        except Exception as e:
            logger.error(f"Error generating temporary TTS: {e}")
            return None
            
    async def disconnect_after_audio(self, voice_client: discord.VoiceClient) -> None:
        """Disconnect from voice channel after audio finishes playing"""
        # Wait a moment to ensure audio is fully played
        await asyncio.sleep(1)

        # Check if still playing
        if voice_client and not voice_client.is_playing():
            await voice_client.disconnect()


class APIManager:
    """Handles all API communication with the AI service"""
    def __init__(self, bot):
        self.bot = bot
        
    async def call_chat_api(
        self,
        user_message: str,
        user_name: str = "User",
        conversation_history: Optional[List[Dict]] = None,
        relevant_info: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """Call the AI API to generate a response with limited conversation history and relevant memories"""
        if not self.bot.ai_client or not self.bot.chat_model:
            return None

        try:
            # Use provided system prompt or build default one
            if system_prompt:
                system_content = system_prompt
            else:
                # Build system prompt with character info
                system_content = f"""You are {self.bot.character_name}.
                    Description: {self.bot.character_description}
                    Scenario: {self.bot.character_scenario}
                    """
                if self.bot.personality_age:
                    system_content += f"Age: {self.bot.personality_age}\n"     
                if self.bot.personality_traits:
                    system_content += f"Character Traits: {self.bot.personality_traits}\n"
                if self.bot.personality_physical_traits:
                    system_content += f"Physical Traits: {self.bot.personality_physical_traits}\n"
                if self.bot.personality_tone:
                    system_content += f"Speaking Tone: {self.bot.personality_tone}\n"
                if self.bot.personality_likes:
                    system_content += f"Likes: {self.bot.personality_likes}\n"
                if self.bot.personality_dislikes:
                    system_content += f"Dislikes: {self.bot.personality_dislikes}\n"
                if self.bot.personality_goals:
                    system_content += f"Goals: {self.bot.personality_goals}\n"
                if self.bot.personality_history:
                    system_content += f"Background: {self.bot.personality_history}\n"
                if self.bot.personality_catchphrases:
                    system_content += f"Signature Phrases: {self.bot.personality_catchphrases}\n"
                    
                # Add conversational examples with substitution
                if self.bot.personality_conversational_examples:
                    examples = self.bot.personality_conversational_examples.replace("{user}", user_name)
                    system_content += f"\nExample Interactions:\n{examples}\n"
                    
                # Add conversational goals with substitution
                if self.bot.personality_conversational_goals:
                    goals = self.bot.personality_conversational_goals.replace("{user}", user_name)
                    system_content += f"\nConversational Goals: {goals}\n"

            # Add custom system prompt if available
            if self.bot.system_prompt:
                system_content = f"{self.bot.system_prompt}\n\n{system_content}"

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
            completion = await self.bot.ai_client.chat.completions.create(
                model=self.bot.chat_model,
                messages=messages,
                stream=False,
            )

            # Extract response text
            response = completion.choices[0].message.content
            return response

        except Exception as e:
            logger.error(f"Error calling chat API: {e}")
            return f"I'm having trouble connecting to my thoughts right now. Please try again later. (Error: {str(e)[:50]}...)"
            
    async def generate_response(
        self,
        user_name: str,
        message_content: str,
        conversation_history: List[Dict],
        relevant_info: List[str] = None,
    ) -> str:
        """Generate a response using the AI API if configured, otherwise fall back to simple responses"""
        # Ensure we only use up to 8 messages of history
        if len(conversation_history) > 8:
            conversation_history = conversation_history[-8:]
        
        # Try to use the API if configured
        if self.bot.ai_client and self.bot.chat_model:
            response = await self.call_chat_api(
                message_content, user_name, conversation_history, relevant_info
            )
            if response:
                return response

        # Fallback to simple response logic
        # Build a prompt using character information and history
        prompt = f"""Character: {self.bot.character_name}
            Description: {self.bot.character_description}
            Scenario: {self.bot.character_scenario}

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
        return f"I understand you're saying something about '{message_content[:20]}...'. As {self.bot.character_name}, I would respond appropriately based on my personality and our conversation history."


class MessageProcessor:
    """Handles message processing, including splitting long messages"""
    def __init__(self, bot):
        self.bot = bot
        # Store for multipart messages
        self.multipart_messages = {}
        # Store for message contexts (for regeneration)
        self.message_contexts = {}
        
    async def send_long_message(
        self, 
        channel: discord.TextChannel, 
        content: str, 
        reference: Optional[discord.Message] = None, 
        reply: bool = True
    ) -> Tuple[discord.Message, Dict]:
        """
        Splits long messages into multiple chunks and sends them.
        Returns the sent message info including all message IDs for tracking.
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
        for msg_id in message_group["message_ids"]:
            self.multipart_messages[msg_id] = message_group
        
        return primary_message, message_group
    
    def save_message_context(self, message_id: int, context: Dict) -> None:
        """Save context for a message for potential regeneration"""
        self.message_contexts[message_id] = context
    
    def get_message_context(self, message_id: int) -> Optional[Dict]:
        """Get the context for a message if it exists"""
        return self.message_contexts.get(message_id)
        
    def get_channel_conversation(self, channel_id: int) -> List[Dict]:
        """Get conversation history for a specific channel, limited to 8 messages"""
        # Initialize conversation storage if not exists
        if not hasattr(self.bot, "channel_conversations"):
            self.bot.channel_conversations = {}

        if channel_id not in self.bot.channel_conversations:
            self.bot.channel_conversations[channel_id] = []

        # Ensure we only keep the last 8 messages
        if len(self.bot.channel_conversations[channel_id]) > 8:
            # Keep only the most recent 8 messages
            self.bot.channel_conversations[channel_id] = self.bot.channel_conversations[channel_id][-8:]
            
        return self.bot.channel_conversations[channel_id]
    
    def save_conversation(self, channel_id: int, conversation: List[Dict]) -> None:
        """Save a conversation to a JSON file"""
        # Create a filename with channel ID and timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{channel_id}_{timestamp}.json"
        filepath = os.path.join(self.bot.conversations_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(conversation, f, indent=2)
            
    def is_multipart_message(self, message_id: int) -> bool:
        """Check if a message is part of a multipart message group"""
        return message_id in self.multipart_messages
        
    def get_message_group(self, message_id: int) -> Optional[Dict]:
        """Get the message group for a message if it's part of a multipart message"""
        return self.multipart_messages.get(message_id)


class LorebookManager:
    """Handles lorebook functionality"""
    def __init__(self, bot):
        self.bot = bot
        self.lorebook_path = os.path.join(bot.data_dir, "lorebook.json")
        self.lorebook_entries = []
        self._load_lorebook()
        
    def _load_lorebook(self):
        """Load lorebook from file"""
        if os.path.exists(self.lorebook_path):
            with open(self.lorebook_path, "r", encoding="utf-8") as f:
                self.lorebook_entries = json.load(f)
        else:
            self.lorebook_entries = []
            self._save_lorebook()
            
    def _save_lorebook(self):
        """Save lorebook to file"""
        with open(self.lorebook_path, "w", encoding="utf-8") as f:
            json.dump(self.lorebook_entries, f, indent=2)
            
    def add_entry(self, keyword: str, content: str) -> None:
        """Add a lorebook entry"""
        self.lorebook_entries.append({
            "keyword": keyword.strip(),
            "content": content.strip()
        })
        self._save_lorebook()
        logger.info(f"Added lorebook entry for keyword: {keyword}")
        
    def remove_entry(self, index: int) -> bool:
        """Remove a lorebook entry by index"""
        if 0 <= index < len(self.lorebook_entries):
            entry = self.lorebook_entries.pop(index)
            self._save_lorebook()
            logger.info(f"Removed lorebook entry for keyword: {entry['keyword']}")
            return True
        return False
        
    def clear_entries(self) -> None:
        """Clear all lorebook entries"""
        self.lorebook_entries = []
        self._save_lorebook()
        logger.info("Cleared all lorebook entries")
        
    def get_relevant_entries(self, message_content: str) -> List[str]:
        """Get lorebook entries relevant to the current message"""
        relevant_entries = []

        for entry in self.lorebook_entries:
            # Check if keyword is in the message
            if entry["keyword"].lower() in message_content.lower():
                relevant_entries.append(entry["content"])
                logger.info(f"Found relevant lorebook entry: {entry['keyword']}")

        return relevant_entries
        
    def format_entries_for_display(self) -> str:
        """Format lorebook entries for display"""
        lore_display = "**Lorebook Entries:**\n"
        if not self.lorebook_entries:
            lore_display += "No entries yet."
        else:
            for i, entry in enumerate(self.lorebook_entries):
                lore_display += f"{i+1}. **{entry['keyword']}**: {entry['content'][:50]}...\n"
        return lore_display


class OpenShapeHelpers:
    """Main class to initialize and integrate all helper components"""
    def __init__(self, bot):
        self.bot = bot
        # Initialize all component managers
        self.memory = MemoryManager(bot)
        self.tts = TTSHandler(bot)
        self.api = APIManager(bot)
        self.messages = MessageProcessor(bot)
        self.lorebook = LorebookManager(bot)
        
        # Replace methods in the bot with our implementations
        # Memory methods
        bot._search_memory = self.memory.search_memory
        bot._update_memory_from_conversation = self.memory.update_memory_from_conversation
        bot._extract_memories_from_text = self.memory.extract_memories_from_text
        
        # TTS methods
        bot._generate_tts = self.tts.generate_tts
        bot._generate_temp_tts = self.tts.generate_temp_tts
        bot._disconnect_after_audio = self.tts.disconnect_after_audio
        bot._extract_speech_text = self.tts._extract_speech_text
        
        # API methods
        bot._call_chat_api = self.api.call_chat_api
        bot._generate_response = self.api.generate_response
        
        # Message processing methods
        bot._send_long_message = self.messages.send_long_message
        bot._get_channel_conversation = self.messages.get_channel_conversation
        bot._save_conversation = self.messages.save_conversation
        
        # Lorebook methods
        bot._get_relevant_lorebook_entries = self.lorebook.get_relevant_entries
        
        # Provide direct access to the managers from the bot
        bot.memory_manager = self.memory
        bot.tts_handler = self.tts
        bot.api_manager = self.api
        bot.message_processor = self.messages
        bot.lorebook_manager = self.lorebook
        bot.multipart_messages = self.messages.multipart_messages
        bot.message_contexts = self.messages.message_contexts

        # Make long_term_memory accessible from the bot
        bot.long_term_memory = self.memory.long_term_memory
        bot.lorebook_entries = self.lorebook.lorebook_entries
        bot._save_memory = self.memory._save_memory
        bot._save_lorebook = self.lorebook._save_lorebook


# Utility function to initialize the helpers
def setup_openshape_helpers(bot):
    return OpenShapeHelpers(bot)