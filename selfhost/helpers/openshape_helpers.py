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
        user_discord_id: Optional[str] = None,
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
                system_content = f"You are {self.bot.character_name}.\nPeople in conversation: {self.bot.character_name}, {user_name}. Your job is to respond to last message from {user_name}. You can use other messages for context but don't directly address them. DO NOT output an empty message. ALWAYS reply. NO EMPTY MESSAGE. you can message many times in a row. just continue the conversation. do not reply with empty message.\nAbout {self.bot.character_name}: {self.bot.character_backstory}\nScenario: {self.bot.character_scenario}\n"
                if self.bot.character_description:
                    system_content += f"Appearance: {self.bot.character_description}\n"
                if self.bot.personality_age:
                    system_content += f"Age: {self.bot.personality_age}\n"     
                if self.bot.personality_traits:
                    system_content += f"Personality Traits: {self.bot.personality_traits}\n"
                if self.bot.personality_physical_traits:
                    system_content += f"Physical Traits: {self.bot.personality_physical_traits}\n"
                if self.bot.personality_tone:
                    system_content += f"Tone: {self.bot.personality_tone}\n"
                if self.bot.personality_likes:
                    system_content += f"Likes: {self.bot.personality_likes}\n"
                if self.bot.personality_dislikes:
                    system_content += f"Dislikes: {self.bot.personality_dislikes}\n"
                if self.bot.personality_history:
                    system_content += f"History: {self.bot.personality_history}\n"
                if self.bot.personality_goals:
                    system_content += f"Personality Goals: {self.bot.personality_goals}\n"
                if self.bot.personality_catchphrases:
                    system_content += f"Signature Phrases: {self.bot.personality_catchphrases}\n"
                    
                # Add conversational goals with substitution
                if self.bot.personality_conversational_goals:
                    goals = self.bot.personality_conversational_goals.replace("{user}", user_name)
                    system_content += f"\nConversational Goals: {goals}\n"
                    
                # Add conversational examples with substitution
                if self.bot.personality_conversational_examples:
                    examples = self.bot.personality_conversational_examples.replace("{user}", user_name)
                    system_content += f"\nConversataional Examples:\n{examples}\n"
                    
                #Add custom system prompt if available
                if self.bot.system_prompt:
                    system_content += f"\nContext:\n{self.bot.system_prompt}\n"

            # Add relevant information (lore and memories) if available
            if relevant_info and len(relevant_info) > 0:
                system_content += f"\n- Long Term Memory:\n- [System Note: You are not AI or Chatbot. You are {self.bot.character_name}.]\n"
                for info in relevant_info:
                    # if not the last item, add a line break
                    if info != relevant_info[-1]:
                        system_content += f"\n- [System Note: {info}]"
                    else:
                        system_content += f"""\n- [System Note: {info}". Do not repeat this information but you can use it for context if needed.]"""
           
            messages = [{"role": "system", "content": system_content}]

            # Add conversation history (limited to available history, max 8 messages)
            if conversation_history:
                history_to_use = conversation_history[-8:] if len(conversation_history) > 8 else conversation_history
                for entry in history_to_use:
                    role = "assistant" if entry["role"] == "assistant" else "user"
                    # Include Discord ID in the message if available
                    content = f"{entry['name']}: {entry['content']}"
                    
                    messages.append({"role": role, "content": content})

            # If the latest message isn't in history, add it
            if not conversation_history or user_message != conversation_history[-1].get("content", ""):
                user_content = f"{user_name}: {user_message}"
                messages.append({"role": "user", "content": user_content})

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
        
        # Get user Discord ID from the last user message if available
        user_discord_id = None
        for entry in reversed(conversation_history):
            if entry["role"] == "user" and "discord_id" in entry:
                user_discord_id = entry["discord_id"]
                break
        
        # Try to use the API if configured
        if self.bot.ai_client and self.bot.chat_model:
            response = await self.call_chat_api(
                message_content, 
                user_name, 
                conversation_history, 
                relevant_info,
                user_discord_id=user_discord_id
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
        self.tts = TTSHandler(bot)
        self.api = APIManager(bot)
        self.messages = MessageProcessor(bot)
        self.lorebook = LorebookManager(bot)
        
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
        bot.tts_handler = self.tts
        bot.api_manager = self.api
        bot.message_processor = self.messages
        bot.lorebook_manager = self.lorebook
        bot.multipart_messages = self.messages.multipart_messages
        bot.message_contexts = self.messages.message_contexts

        # Make long_term_memory accessible from the bot
        bot.lorebook_entries = self.lorebook.lorebook_entries
        bot._save_lorebook = self.lorebook._save_lorebook


# Utility function to initialize the helpers
def setup_openshape_helpers(bot):
    return OpenShapeHelpers(bot)