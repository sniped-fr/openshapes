import json
import os
import logging
import datetime
import re
import asyncio
import hashlib
import discord
from typing import Dict, List, Optional, Tuple, Any, TypeVar

logger = logging.getLogger("openshape.helpers")

T = TypeVar('T')

class TextProcessor:
    @staticmethod
    def extract_speech_text(text: str, ignore_asterisks: bool = False, only_narrate_quotes: bool = False) -> str:
        result = text
        if ignore_asterisks:
            result = re.sub(r'\*[^*]*\*', '', result)
        
        if only_narrate_quotes:
            quotes = re.findall(r'"([^"]*)"', result)
            if quotes:
                result = '... '.join(quotes)
            else:
                result = ''
        
        return ' '.join(result.split())
        
    @staticmethod
    def split_into_chunks(content: str, max_length: int = 2000) -> List[str]:
        if len(content) <= max_length:
            return [content]
            
        chunks = []
        current_chunk = ""
        paragraphs = content.split('\n\n')
        
        for paragraph in paragraphs:
            if len(paragraph) > max_length:
                sentences = paragraph.replace('. ', '.\n').split('\n')
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 > max_length:
                        chunks.append(current_chunk)
                        current_chunk = sentence + '\n\n'
                    else:
                        current_chunk += sentence + '\n\n'
            else:
                if len(current_chunk) + len(paragraph) + 2 > max_length:
                    chunks.append(current_chunk)
                    current_chunk = paragraph + '\n\n'
                else:
                    current_chunk += paragraph + '\n\n'
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

class AudioFileManager:
    def __init__(self, base_dir: str):
        self.audio_dir = os.path.join(base_dir, "audio")
        self.temp_dir = os.path.join(base_dir, "temp_audio")
        os.makedirs(self.audio_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def get_persistent_filepath(self, character_name: str, text: str) -> str:
        text_hash = hashlib.md5(text.encode()).hexdigest()[:10]
        filename = f"{character_name}_{text_hash}.mp3"
        return os.path.join(self.audio_dir, filename)
        
    def get_temporary_filepath(self, character_name: str) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{character_name}_{timestamp}.mp3"
        return os.path.join(self.temp_dir, filename)

class TTSHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        self.file_manager = AudioFileManager(bot.data_dir)
        
    async def generate_tts(self, text: str) -> Optional[str]:
        if (
            not self.bot.api_integration.client
            or not self.bot.api_integration.tts_model
            or not self.bot.api_integration.tts_voice
            or not self.bot.use_tts
        ):
            return None

        try:
            speech_text = TextProcessor.extract_speech_text(
                text,
                ignore_asterisks=True,
                only_narrate_quotes=True
            )
            
            if not speech_text:
                return None
            
            filepath = self.file_manager.get_persistent_filepath(self.bot.character_name, text)

            if os.path.exists(filepath):
                return filepath

            response = await self.bot.api_integration.client.audio.speech.create(
                model=self.bot.api_integration.tts_model, voice=self.bot.api_integration.tts_voice, input=speech_text
            )

            response.stream_to_file(filepath)
            return filepath

        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None
            
    async def generate_temp_tts(self, text: str) -> Optional[str]:
        if (
            not self.bot.api_integration.client
            or not self.bot.api_integration.tts_model
            or not self.bot.api_integration.tts_voice
            or not self.bot.use_tts
        ):
            return None

        try:
            speech_text = TextProcessor.extract_speech_text(text, ignore_asterisks=True)
            
            if not speech_text:
                return None
                
            filepath = self.file_manager.get_temporary_filepath(self.bot.character_name)

            response = await self.bot.api_integration.client.audio.speech.create(
                model=self.bot.api_integration.tts_model, voice=self.bot.api_integration.tts_voice, input=speech_text
            )

            response.stream_to_file(filepath)
            return filepath

        except Exception as e:
            logger.error(f"Error generating temporary TTS: {e}")
            return None
            
    async def disconnect_after_audio(self, voice_client: discord.VoiceClient) -> None:
        await asyncio.sleep(1)

        if voice_client and not voice_client.is_playing():
            await voice_client.disconnect()

class SystemPromptBuilder:
    def __init__(self, bot: Any):
        self.bot = bot
        
    def build_prompt(self, user_name: str, relevant_info: Optional[List[str]] = None) -> str:
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
            
        if self.bot.personality_conversational_goals:
            goals = self.bot.personality_conversational_goals.replace("{user}", user_name)
            system_content += f"\nConversational Goals: {goals}\n"
            
        if self.bot.personality_conversational_examples:
            examples = self.bot.personality_conversational_examples.replace("{user}", user_name)
            system_content += f"\nConversataional Examples:\n{examples}\n"
            
        if self.bot.system_prompt:
            system_content += f"\nContext:\n{self.bot.system_prompt}\n"
            
        if relevant_info and len(relevant_info) > 0:
            system_content += f"\n- Long Term Memory:\n- [System Note: You are not AI or Chatbot. You are {self.bot.character_name}.]\n"
            for info in relevant_info:
                if info != relevant_info[-1]:
                    system_content += f"\n- [System Note: {info}]"
                else:
                    system_content += f"""\n- [System Note: {info}". Do not repeat this information but you can use it for context if needed.]"""
                    
        return system_content

class MessageFormatter:
    @staticmethod
    def format_user_message(user_name: str, content: str) -> Dict[str, str]:
        return {
            "role": "user",
            "content": f"{user_name}: {content}"
        }
        
    @staticmethod
    def format_assistant_message(name: str, content: str) -> Dict[str, str]:
        return {
            "role": "assistant",
            "content": f"{name}: {content}"
        }
        
    @staticmethod
    def format_system_message(content: str) -> Dict[str, str]:
        return {
            "role": "system",
            "content": content
        }

class APIManager:
    def __init__(self, bot: Any):
        self.bot = bot
        self.prompt_builder = SystemPromptBuilder(bot)
        
    async def call_chat_api(
        self,
        user_message: str,
        user_name: str = "User",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        relevant_info: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        if not self.bot.api_integration.client or not self.bot.api_integration.chat_model:
            return None

        try:
            system_content = system_prompt if system_prompt else self.prompt_builder.build_prompt(user_name, relevant_info)
            messages = [MessageFormatter.format_system_message(system_content)]

            if conversation_history:
                history_to_use = conversation_history[-8:] if len(conversation_history) > 8 else conversation_history
                for entry in history_to_use:
                    if entry["role"] == "assistant":
                        messages.append(MessageFormatter.format_assistant_message(entry["name"], entry["content"]))
                    else:
                        messages.append(MessageFormatter.format_user_message(entry["name"], entry["content"]))

            if not conversation_history or user_message != conversation_history[-1].get("content", ""):
                messages.append(MessageFormatter.format_user_message(user_name, user_message))

            completion = await self.bot.api_integration.client.chat.completions.create(
                model=self.bot.api_integration.chat_model,
                messages=messages,
                stream=False,
            )

            return completion.choices[0].message.content

        except Exception as e:
            logger.error(f"Error calling chat API: {e}")
            return f"I'm having trouble connecting to my thoughts right now. Please try again later. (Error: {str(e)[:50]}...)"
            
    async def generate_response(
        self,
        user_name: str,
        message_content: str,
        conversation_history: List[Dict[str, Any]],
        relevant_info: Optional[List[str]] = None,
    ) -> str:
        if len(conversation_history) > 8:
            conversation_history = conversation_history[-8:]
        
        if self.bot.api_integration.client and self.bot.api_integration.chat_model:
            response = await self.call_chat_api(
                message_content,
                user_name,
                conversation_history,
                relevant_info
            )
            if response:
                return response
            
        prompt = f"""Character: {self.bot.character_name}
            Description: {self.bot.character_description}
            Scenario: {self.bot.character_scenario}

            User: {user_name}
            Message: {message_content}
            """
            
        if relevant_info and len(relevant_info) > 0:
            prompt += "Relevant information:\n"
            for info in relevant_info:
                prompt += f"- {info}\n"

        history_to_use = conversation_history[:-1]
        if history_to_use:
            prompt += "\nRecent conversation:\n"
            for entry in history_to_use:
                prompt += f"{entry['name']}: {entry['content']}\n"

        greeting_words = ["hello", "hi", "hey", "greetings", "howdy"]
        if any(word in message_content.lower() for word in greeting_words):
            return f"Hello {user_name}! How can I help you today?"

        if "?" in message_content:
            return "That's an interesting question! Let me think about that..."

        return f"I understand you're saying something about '{message_content[:20]}...'. As {self.bot.character_name}, I would respond appropriately based on my personality and our conversation history."

class MessageGroup:
    def __init__(self, content: str):
        self.is_multipart = False
        self.message_ids: List[int] = []
        self.primary_id: Optional[int] = None
        self.content = content
        
    def add_message_id(self, message_id: int, is_primary: bool = False) -> None:
        self.message_ids.append(message_id)
        if is_primary:
            self.primary_id = message_id
            
    def mark_as_multipart(self) -> None:
        self.is_multipart = True
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_multipart": self.is_multipart,
            "message_ids": self.message_ids,
            "primary_id": self.primary_id,
            "content": self.content
        }

class MessageProcessor:
    def __init__(self, bot: Any):
        self.bot = bot
        self.multipart_messages: Dict[int, Dict[str, Any]] = {}
        self.message_contexts: Dict[int, Dict[str, Any]] = {}
        
    async def send_long_message(
        self,
        channel: discord.TextChannel,
        content: str,
        reference: Optional[discord.Message] = None,
        reply: bool = True
    ) -> Tuple[discord.Message, Dict[str, Any]]:
        MAX_LENGTH = 2000
        message_group = MessageGroup(content)
        
        if len(content) <= MAX_LENGTH:
            if reference:
                sent_message = await reference.reply(content, mention_author=reply)
            else:
                sent_message = await channel.send(content)
                
            message_group.add_message_id(sent_message.id, True)
            group_dict = message_group.to_dict()
            self.multipart_messages[sent_message.id] = group_dict
            return sent_message, group_dict
        
        message_group.mark_as_multipart()
        chunks = TextProcessor.split_into_chunks(content, MAX_LENGTH)
        chunks = [f"{chunk}\n{'(continued...)' if i < len(chunks) - 1 else ''}" for i, chunk in enumerate(chunks)]
        
        primary_message = None
        all_messages: List[discord.Message] = []
        
        for i, chunk in enumerate(chunks):
            if i == 0 and reference:
                sent_message = await reference.reply(chunk, mention_author=reply)
                primary_message = sent_message
                message_group.add_message_id(sent_message.id, True)
            else:
                sent_message = await channel.send(chunk)
                message_group.add_message_id(sent_message.id)
            
            all_messages.append(sent_message)
        
        if primary_message is None and all_messages:
            primary_message = all_messages[0]
            message_group.primary_id = primary_message.id
        
        group_dict = message_group.to_dict()
        for msg_id in message_group.message_ids:
            self.multipart_messages[msg_id] = group_dict
        
        return primary_message or all_messages[0], group_dict
    
    def save_message_context(self, message_id: int, context: Dict[str, Any]) -> None:
        self.message_contexts[message_id] = context
    
    def get_message_context(self, message_id: int) -> Optional[Dict[str, Any]]:
        return self.message_contexts.get(message_id)
        
    def get_channel_conversation(self, channel_id: int) -> List[Dict[str, Any]]:
        if not hasattr(self.bot, "channel_conversations"):
            self.bot.channel_conversations = {}

        if channel_id not in self.bot.channel_conversations:
            self.bot.channel_conversations[channel_id] = []

        if len(self.bot.channel_conversations[channel_id]) > 8:
            self.bot.channel_conversations[channel_id] = self.bot.channel_conversations[channel_id][-8:]
            
        return self.bot.channel_conversations[channel_id]
    
    def save_conversation(self, channel_id: int, conversation: List[Dict[str, Any]]) -> None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{channel_id}_{timestamp}.json"
        filepath = os.path.join(self.bot.conversations_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(conversation, f, indent=2)
            
    def is_multipart_message(self, message_id: int) -> bool:
        return message_id in self.multipart_messages
        
    def get_message_group(self, message_id: int) -> Optional[Dict[str, Any]]:
        return self.multipart_messages.get(message_id)

class LorebookEntry:
    def __init__(self, keyword: str, content: str):
        self.keyword = keyword.strip()
        self.content = content.strip()
        
    def to_dict(self) -> Dict[str, str]:
        return {
            "keyword": self.keyword,
            "content": self.content
        }

class LorebookManager:
    def __init__(self, bot: Any):
        self.bot = bot
        self.lorebook_path = os.path.join(bot.data_dir, "lorebook.json")
        self.lorebook_entries: List[Dict[str, str]] = []
        self._load_lorebook()
        
    def _load_lorebook(self) -> None:
        if os.path.exists(self.lorebook_path):
            with open(self.lorebook_path, "r", encoding="utf-8") as f:
                self.lorebook_entries = json.load(f)
        else:
            self.lorebook_entries = []
            self._save_lorebook()
            
    def _save_lorebook(self) -> None:
        with open(self.lorebook_path, "w", encoding="utf-8") as f:
            json.dump(self.lorebook_entries, f, indent=2)
            
    def add_entry(self, keyword: str, content: str) -> None:
        entry = LorebookEntry(keyword, content)
        self.lorebook_entries.append(entry.to_dict())
        self._save_lorebook()
        logger.info(f"Added lorebook entry for keyword: {keyword}")
        
    def remove_entry(self, index: int) -> bool:
        if 0 <= index < len(self.lorebook_entries):
            entry = self.lorebook_entries.pop(index)
            self._save_lorebook()
            logger.info(f"Removed lorebook entry for keyword: {entry['keyword']}")
            return True
        return False
        
    def clear_entries(self) -> None:
        self.lorebook_entries = []
        self._save_lorebook()
        logger.info("Cleared all lorebook entries")
        
    def get_relevant_entries(self, message_content: str) -> List[str]:
        relevant_entries = []

        for entry in self.lorebook_entries:
            if entry["keyword"].lower() in message_content.lower():
                relevant_entries.append(entry["content"])
                logger.info(f"Found relevant lorebook entry: {entry['keyword']}")

        return relevant_entries
        
    def format_entries_for_display(self) -> str:
        lore_display = "**Lorebook Entries:**\n"
        if not self.lorebook_entries:
            lore_display += "No entries yet."
        else:
            for i, entry in enumerate(self.lorebook_entries):
                lore_display += f"{i+1}. **{entry['keyword']}**: {entry['content'][:50]}...\n"
        return lore_display

class OpenShapeHelpers:
    def __init__(self, bot: Any):
        self.bot = bot
        self.tts = TTSHandler(bot)
        self.api = APIManager(bot)
        self.messages = MessageProcessor(bot)
        self.lorebook = LorebookManager(bot)
        
        self._register_methods()
        
    def _register_methods(self) -> None:
        self.bot._is_multipart_message = self.messages.is_multipart_message

        self.bot._generate_tts = self.tts.generate_tts
        self.bot._generate_temp_tts = self.tts.generate_temp_tts
        self.bot._disconnect_after_audio = self.tts.disconnect_after_audio
        self.bot._extract_speech_text = TextProcessor.extract_speech_text
        
        self.bot._call_chat_api = self.api.call_chat_api
        self.bot._generate_response = self.api.generate_response
        
        self.bot._send_long_message = self.messages.send_long_message
        self.bot._get_channel_conversation = self.messages.get_channel_conversation
        self.bot._save_conversation = self.messages.save_conversation
        self.bot._save_message_context = self.messages.save_message_context

        self.bot._get_message_context = self.messages.get_message_context
        self.bot._get_message_group = self.messages.get_message_group

        self.bot._get_relevant_lorebook_entries = self.lorebook.get_relevant_entries
        
        self.bot.tts_handler = self.tts
        self.bot.api_manager = self.api
        self.bot.message_processor = self.messages
        self.bot.lorebook_manager = self.lorebook
        self.bot.multipart_messages = self.messages.multipart_messages
        self.bot.message_contexts = self.messages.message_contexts

        self.bot.lorebook_entries = self.lorebook.lorebook_entries
        self.bot._save_lorebook = self.lorebook._save_lorebook