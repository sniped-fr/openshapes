import json
import os
import logging
import datetime
import re
import asyncio
import hashlib
import discord
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("openshape.helpers")

class TTSHandler:
    def __init__(self, bot):
        self.bot = bot
        self.audio_dir = os.path.join(bot.data_dir, "audio")
        os.makedirs(self.audio_dir, exist_ok=True)
        self.temp_dir = os.path.join(bot.data_dir, "temp_audio")
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def _extract_speech_text(self, text: str, ignore_asterisks: bool = False, only_narrate_quotes: bool = False) -> str:
        result = text
        if ignore_asterisks:
            result = re.sub(r'\*[^*]*\*', '', result)
        
        if only_narrate_quotes:
            quotes = re.findall(r'"([^"]*)"', result)
            if quotes:
                result = '... '.join(quotes)
            else:
                result = ''
        
        result = ' '.join(result.split())
    
        return result
        
    async def generate_tts(self, text: str) -> Optional[str]:
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
            
            text_hash = hashlib.md5(text.encode()).hexdigest()[:10]
            filename = f"{self.bot.character_name}_{text_hash}.mp3"
            filepath = os.path.join(self.audio_dir, filename)

            if os.path.exists(filepath):
                return filepath

            response = await self.bot.ai_client.audio.speech.create(
                model=self.bot.tts_model, voice=self.bot.tts_voice, input=speech_text
            )

            response.stream_to_file(filepath)
            return filepath

        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None
            
    async def generate_temp_tts(self, text: str) -> Optional[str]:
        if (
            not self.bot.ai_client
            or not self.bot.tts_model
            or not self.bot.tts_voice
            or not self.bot.use_tts
        ):
            return None

        try:
            speech_text = self._extract_speech_text(text, ignore_asterisks=True)
            
            if not speech_text:
                return None
                
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{self.bot.character_name}_{timestamp}.mp3"
            filepath = os.path.join(self.temp_dir, filename)

            response = await self.bot.ai_client.audio.speech.create(
                model=self.bot.tts_model, voice=self.bot.tts_voice, input=speech_text
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


class APIManager:
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
        if not self.bot.ai_client or not self.bot.chat_model:
            return None

        try:
            if system_prompt:
                system_content = system_prompt
            else:
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
           
            messages = [{"role": "system", "content": system_content}]

            if conversation_history:
                history_to_use = conversation_history[-8:] if len(conversation_history) > 8 else conversation_history
                for entry in history_to_use:
                    role = "assistant" if entry["role"] == "assistant" else "user"
                    content = f"{entry['name']}: {entry['content']}"
                    
                    messages.append({"role": role, "content": content})

            if not conversation_history or user_message != conversation_history[-1].get("content", ""):
                user_content = f"{user_name}: {user_message}"
                messages.append({"role": "user", "content": user_content})

            completion = await self.bot.ai_client.chat.completions.create(
                model=self.bot.chat_model,
                messages=messages,
                stream=False,
            )

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
        if len(conversation_history) > 8:
            conversation_history = conversation_history[-8:]
        
        user_discord_id = None
        for entry in reversed(conversation_history):
            if entry["role"] == "user" and "discord_id" in entry:
                user_discord_id = entry["discord_id"]
                break
        
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


class MessageProcessor:
    def __init__(self, bot):
        self.bot = bot
        self.multipart_messages = {}
        self.message_contexts = {}
        
    async def send_long_message(
        self, 
        channel: discord.TextChannel, 
        content: str, 
        reference: Optional[discord.Message] = None, 
        reply: bool = True
    ) -> Tuple[discord.Message, Dict]:
        MAX_LENGTH = 2000
        
        message_group = {
            "is_multipart": False,
            "message_ids": [],
            "primary_id": None,
            "content": content
        }
        
        if len(content) <= MAX_LENGTH:
            if reference:
                sent_message = await reference.reply(content, mention_author=reply)
            else:
                sent_message = await channel.send(content)
                
            message_group["message_ids"].append(sent_message.id)
            message_group["primary_id"] = sent_message.id
            return sent_message, message_group
        
        message_group["is_multipart"] = True
        
        chunks = []
        current_chunk = ""
        
        paragraphs = content.split('\n\n')
        
        for paragraph in paragraphs:
            if len(paragraph) > MAX_LENGTH:
                sentences = paragraph.replace('. ', '.\n').split('\n')
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 > MAX_LENGTH:
                        chunks.append(current_chunk)
                        current_chunk = sentence + '\n\n'
                    else:
                        current_chunk += sentence + '\n\n'
            else:
                if len(current_chunk) + len(paragraph) + 2 > MAX_LENGTH:
                    chunks.append(current_chunk)
                    current_chunk = paragraph + '\n\n'
                else:
                    current_chunk += paragraph + '\n\n'
        
        if current_chunk:
            chunks.append(current_chunk)
        
        primary_message = None
        all_messages = []
        
        chunks = [f"{chunk}\n{'(continued...)' if i < len(chunks) - 1 else ''}" for i, chunk in enumerate(chunks)]
        
        for i, chunk in enumerate(chunks):
            if i == 0 and reference:
                sent_message = await reference.reply(chunk, mention_author=reply)
                primary_message = sent_message
            else:
                sent_message = await channel.send(chunk)
            
            all_messages.append(sent_message)
            message_group["message_ids"].append(sent_message.id)
        
        if primary_message is None and all_messages:
            primary_message = all_messages[0]
        
        message_group["primary_id"] = primary_message.id if primary_message else None
        
        for msg_id in message_group["message_ids"]:
            self.multipart_messages[msg_id] = message_group
        
        return primary_message, message_group
    
    def save_message_context(self, message_id: int, context: Dict) -> None:
        self.message_contexts[message_id] = context
    
    def get_message_context(self, message_id: int) -> Optional[Dict]:
        return self.message_contexts.get(message_id)
        
    def get_channel_conversation(self, channel_id: int) -> List[Dict]:
        if not hasattr(self.bot, "channel_conversations"):
            self.bot.channel_conversations = {}

        if channel_id not in self.bot.channel_conversations:
            self.bot.channel_conversations[channel_id] = []

        if len(self.bot.channel_conversations[channel_id]) > 8:
            self.bot.channel_conversations[channel_id] = self.bot.channel_conversations[channel_id][-8:]
            
        return self.bot.channel_conversations[channel_id]
    
    def save_conversation(self, channel_id: int, conversation: List[Dict]) -> None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{channel_id}_{timestamp}.json"
        filepath = os.path.join(self.bot.conversations_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(conversation, f, indent=2)
            
    def is_multipart_message(self, message_id: int) -> bool:
        return message_id in self.multipart_messages
        
    def get_message_group(self, message_id: int) -> Optional[Dict]:
        return self.multipart_messages.get(message_id)


class LorebookManager:
    def __init__(self, bot):
        self.bot = bot
        self.lorebook_path = os.path.join(bot.data_dir, "lorebook.json")
        self.lorebook_entries = []
        self._load_lorebook()
        
    def _load_lorebook(self):
        if os.path.exists(self.lorebook_path):
            with open(self.lorebook_path, "r", encoding="utf-8") as f:
                self.lorebook_entries = json.load(f)
        else:
            self.lorebook_entries = []
            self._save_lorebook()
            
    def _save_lorebook(self):
        with open(self.lorebook_path, "w", encoding="utf-8") as f:
            json.dump(self.lorebook_entries, f, indent=2)
            
    def add_entry(self, keyword: str, content: str) -> None:
        self.lorebook_entries.append({
            "keyword": keyword.strip(),
            "content": content.strip()
        })
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
    def __init__(self, bot):
        self.bot = bot
        self.tts = TTSHandler(bot)
        self.api = APIManager(bot)
        self.messages = MessageProcessor(bot)
        self.lorebook = LorebookManager(bot)
        
        bot._generate_tts = self.tts.generate_tts
        bot._generate_temp_tts = self.tts.generate_temp_tts
        bot._disconnect_after_audio = self.tts.disconnect_after_audio
        bot._extract_speech_text = self.tts._extract_speech_text
        
        bot._call_chat_api = self.api.call_chat_api
        bot._generate_response = self.api.generate_response
        
        bot._send_long_message = self.messages.send_long_message
        bot._get_channel_conversation = self.messages.get_channel_conversation
        bot._save_conversation = self.messages.save_conversation
        
        bot._get_relevant_lorebook_entries = self.lorebook.get_relevant_entries
        
        bot.tts_handler = self.tts
        bot.api_manager = self.api
        bot.message_processor = self.messages
        bot.lorebook_manager = self.lorebook
        bot.multipart_messages = self.messages.multipart_messages
        bot.message_contexts = self.messages.message_contexts

        bot.lorebook_entries = self.lorebook.lorebook_entries
        bot._save_lorebook = self.lorebook._save_lorebook