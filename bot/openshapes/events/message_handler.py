import discord
import re
import os
import datetime
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger("openshape")

class MessageContext:
    def __init__(
        self, 
        user_name: str, 
        user_message: str, 
        channel_history: List[Dict[str, Any]], 
        relevant_info: List[str], 
        original_message_id: int, 
        user_discord_id: str
    ):
        self.user_name = user_name
        self.user_message = user_message
        self.channel_history = channel_history
        self.relevant_info = relevant_info
        self.original_message_id = original_message_id
        self.user_discord_id = user_discord_id
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_name": self.user_name,
            "user_message": self.user_message,
            "channel_history": self.channel_history,
            "relevant_info": self.relevant_info,
            "original_message": self.original_message_id,
            "user_discord_id": self.user_discord_id
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageContext':
        return cls(
            user_name=data["user_name"],
            user_message=data["user_message"],
            channel_history=data["channel_history"],
            relevant_info=data["relevant_info"],
            original_message_id=data["original_message"],
            user_discord_id=data["user_discord_id"]
        )

class ResponseGenerator:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def generate_response(
        self, 
        channel_history: List[Dict[str, Any]], 
        relevant_info: List[str],
        user_message: str = ""
    ) -> str:
        if not self.bot.api_integration.client or not self.bot.api_integration.chat_model:
            return "I apologize, but my AI client is not configured correctly. Please ask my owner to set up API settings."
            
        try:
            messages = [{"role": "system", "content": self.bot.system_prompt}]
            
            if relevant_info:
                info_text = "Relevant information:\n" + "\n".join(relevant_info)
                messages.append({"role": "system", "content": info_text})
            
            history_to_use = channel_history[-8:] if len(channel_history) > 8 else channel_history
            for msg in history_to_use:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
                
            if user_message and (not channel_history or user_message != channel_history[-1].get("content", "")):
                messages.append({"role": "user", "content": user_message})
            
            completion = await self.bot.api_integration.client.chat.completions.create(
                model=self.bot.api_integration.chat_model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
            )
            
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"I'm having trouble connecting to my thoughts right now. Please try again later. (Error: {str(e)[:50]}...)"

class TTSPlayback:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def play_audio(self, message: discord.Message, text: str) -> Optional[str]:
        if (not self.bot.use_tts or 
            not hasattr(self.bot, 'tts_handler') or 
            not message.guild or 
            not message.author.voice or 
            not message.author.voice.channel):
            return None
            
        try:
            temp_audio_file = await self.bot.tts_handler.generate_temp_tts(text)
            if not temp_audio_file:
                return None
                
            voice_channel = message.author.voice.channel
            voice_client = message.guild.voice_client
            
            if voice_client:
                if voice_client.channel != voice_channel:
                    await voice_client.move_to(voice_channel)
            else:
                voice_client = await voice_channel.connect()

            def after_playing(error: Optional[Exception]) -> None:
                try:
                    os.remove(temp_audio_file)
                    logger.info(f"Deleted temporary TTS file: {temp_audio_file}")
                except Exception as e:
                    logger.error(f"Error deleting temporary TTS file: {e}")
                
                asyncio.run_coroutine_threadsafe(
                    self.bot.tts_handler.disconnect_after_audio(voice_client),
                    self.bot.loop,
                )

            voice_client.play(
                discord.FFmpegPCMAudio(temp_audio_file),
                after=after_playing,
            )
            
            return temp_audio_file
        except Exception as e:
            logger.error(f"Error playing TTS audio: {e}")
            return None

class MessageHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        self.response_generator = ResponseGenerator(bot)
        self.tts_playback = TTSPlayback(bot)
        
    async def _should_respond(self, message: discord.Message) -> Tuple[bool, bool]:
        should_respond = False
        is_priority = False

        if self.bot.always_reply_mentions and self.bot.user in message.mentions:
            should_respond = True
            is_priority = True
        elif (hasattr(message, 'reference') and 
              message.reference and 
              message.reference.resolved and 
              message.reference.resolved.author.id == self.bot.user.id):
            should_respond = True
            is_priority = True
        elif self.bot.reply_to_name and self.bot.character_name.lower() in message.content.lower():
            should_respond = True
            is_priority = True
        elif message.channel.id in self.bot.activated_channels:
            current_time = datetime.datetime.now().timestamp()
            last_time = self.bot.channel_last_message_time.get(message.channel.id, 0)
            time_since_last_message = current_time - last_time
            
            if time_since_last_message >= self.bot.message_cooldown_seconds:
                should_respond = True
                self.bot.channel_last_message_time[message.channel.id] = current_time
                
        return should_respond, is_priority
        
    async def process_attachments(self, message: discord.Message) -> str:
        file_content = await self.bot.file_parser.process_attachments(message)
        return f"\n\n{file_content}" if file_content else ""
        
    def process_text_with_regex(self, text: str, context_type: str, message: discord.Message) -> str:
        if not hasattr(self.bot, 'regex_manager'):
            return text
            
        macros = {
            "user": message.author.display_name,
            "char": self.bot.character_name,
            "server": message.guild.name if message.guild else "DM",
            "channel": message.channel.name if hasattr(message.channel, 'name') else "DM"
        }
        
        return self.bot.regex_manager.process_text(text, context_type, macros=macros)
        
    def get_guild_id(self, message: discord.Message) -> str:
        return str(message.guild.id) if message.guild else "global"
        
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user:
            return

        await self.bot.process_commands(message)

        if message.author.id in self.bot.blacklisted_users:
            return

        should_respond, is_priority = await self._should_respond(message)

        is_ooc = message.content.startswith("//") or message.content.startswith("/ooc")
        if is_ooc and str(message.user.id) == self.bot.config_manager.get("owner_id"):
            await self.bot._handle_ooc_command(message)
            return

        if is_priority and message.channel.id in self.bot.activated_channels:
            self.bot.channel_last_message_time[message.channel.id] = datetime.datetime.now().timestamp()
        
        processed_content = self.process_text_with_regex(message.content, "user_input", message)

        if should_respond:
            async with message.channel.typing():
                guild_id = self.get_guild_id(message)
                attachment_content = await self.process_attachments(message)
                clean_content = re.sub(r"<@!?(\d+)>", "", processed_content).strip()
                clean_content = attachment_content + clean_content

                channel_history = self.bot._get_channel_conversation(message.channel.id)
                
                channel_history.append({
                    "role": "user",
                    "name": message.author.display_name,
                    "content": clean_content,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "discord_id": str(message.author.id),
                })
             
                if len(channel_history) > 8:
                    channel_history = channel_history[-8:]

                relevant_lore = []
                if hasattr(self.bot, 'lorebook_manager'):
                    relevant_lore = self.bot.lorebook_manager.get_relevant_entries(clean_content)
                
                relevant_memories = []
                if hasattr(self.bot, 'memory_manager'):
                    relevant_memories = self.bot.memory_manager.search_memory(clean_content, guild_id)
                
                relevant_info = []
                if relevant_lore:
                    relevant_info.extend(relevant_lore)
                if relevant_memories:
                    relevant_info.extend(relevant_memories)

                response = await self.response_generator.generate_response(
                    channel_history, relevant_info
                )
                
                if hasattr(self.bot, 'regex_manager'):
                    response = self.process_text_with_regex(response, "ai_response", message)

                channel_history.append({
                    "role": "assistant",
                    "name": self.bot.character_name,
                    "content": response,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "discord_id": str(self.bot.user.id),
                })
                
                if len(channel_history) > 8:
                    channel_history = channel_history[-8:]

                if hasattr(self.bot, 'memory_manager'):
                    await self.bot.memory_manager.update_memory_from_conversation(
                        message.author.display_name, clean_content, response, guild_id
                    )

                self.bot._save_conversation(message.channel.id, channel_history)

                formatted_response = (
                    f"**{self.bot.character_name}**: {response}"
                    if self.bot.add_character_name
                    else response
                )
                
                await self.tts_playback.play_audio(message, response)
                
                sent_message, message_group = await self.bot._send_long_message(
                    message.channel,
                    formatted_response,
                    reference=message,
                    reply=True
                )

                await sent_message.add_reaction("🗑️")
                await sent_message.add_reaction("♻️")

                context = MessageContext(
                    user_name=message.author.display_name,
                    user_message=clean_content,
                    channel_history=channel_history[:-1],
                    relevant_info=relevant_info,
                    original_message_id=message.id,
                    user_discord_id=str(message.author.id)
                )
                
                primary_id = message_group["primary_id"]
                if primary_id:
                    self.bot._save_message_context(primary_id, context.to_dict())

class ReactionHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        self.response_generator = ResponseGenerator(bot)
        
    async def handle_delete_reaction(self, reaction: discord.Reaction, message_group: Optional[Dict[str, Any]]) -> None:
        if message_group and message_group["is_multipart"]:
            for msg_id in message_group["message_ids"]:
                try:
                    msg = await reaction.message.channel.fetch_message(msg_id)
                    await msg.delete()
                except (discord.NotFound, discord.HTTPException):
                    continue
        else:
            await reaction.message.delete()
            
    async def handle_regenerate_reaction(
        self, 
        reaction: discord.Reaction, 
        message_group: Optional[Dict[str, Any]],
        message_id: int
    ) -> None:
        if not message_group:
            return
            
        context_message_id = message_id
        if message_group and message_group["primary_id"]:
            context_message_id = message_group["primary_id"]
            
        context_dict = self.bot._get_message_context(context_message_id)
        if not context_dict:
            return
            
        context = MessageContext.from_dict(context_dict)
        
        async with reaction.message.channel.typing():
            response = await self.response_generator.generate_response(
                context.channel_history, context.relevant_info, context.user_message
            )
            
            if hasattr(self.bot, 'regex_manager'):
                macros = {
                    "user": context.user_name,
                    "char": self.bot.character_name,
                    "server": reaction.message.guild.name if reaction.message.guild else "DM",
                    "channel": reaction.message.channel.name if hasattr(reaction.message.channel, 'name') else "DM"
                }
                
                response = self.bot.regex_manager.process_text(
                    response, "ai_response", macros=macros
                )
            
            formatted_response = (
                f"**{self.bot.character_name}**: {response}"
                if self.bot.add_character_name
                else response
            )
            
            await self.send_regenerated_response(
                reaction, context, formatted_response, message_group, response
            )

    async def send_regenerated_response(
        self,
        reaction: discord.Reaction,
        context: MessageContext,
        formatted_response: str,
        message_group: Dict[str, Any],
        response: str
    ) -> None:
        if message_group and message_group["is_multipart"]:
            for msg_id in message_group["message_ids"]:
                try:
                    msg = await reaction.message.channel.fetch_message(msg_id)
                    await msg.delete()
                except (discord.NotFound, discord.HTTPException):
                    continue
            
            try:
                original_message = await reaction.message.channel.fetch_message(context.original_message_id)
                
                primary_message, _ = await self.bot._send_long_message(
                    reaction.message.channel, 
                    formatted_response,
                    reference=original_message
                )
                
                await primary_message.add_reaction("🗑️")
                await primary_message.add_reaction("🔄")
                
                self.bot._save_message_context(primary_message.id, context.to_dict())
                
            except (discord.NotFound, discord.HTTPException):
                primary_message, _ = await self.bot._send_long_message(
                    reaction.message.channel, 
                    formatted_response
                )
                await primary_message.add_reaction("🗑️")
                await primary_message.add_reaction("🔄")
        else:
            try:
                await reaction.message.edit(content=formatted_response)
                edited_message = reaction.message
                
                await edited_message.add_reaction("🔄")
                
            except discord.HTTPException:
                await reaction.message.delete()
                
                try:
                    original_message = await reaction.message.channel.fetch_message(context.original_message_id)
                    
                    primary_message, _ = await self.bot._send_long_message(
                        reaction.message.channel, 
                        formatted_response,
                        reference=original_message
                    )
                    
                    await primary_message.add_reaction("🗑️")
                    await primary_message.add_reaction("🔄")
                    
                    self.bot._save_message_context(primary_message.id, context.to_dict())
                    
                except (discord.NotFound, discord.HTTPException):
                    primary_message, _ = await self.bot._send_long_message(
                        reaction.message.channel, 
                        formatted_response
                    )
                    await primary_message.add_reaction("🗑️")
        
        self.update_channel_history(reaction.message.channel.id, response, context)

    def update_channel_history(self, channel_id: int, response: str, context: MessageContext) -> None:
        channel_history = self.bot._get_channel_conversation(channel_id)
        
        if channel_history and channel_history[-1]["role"] == "assistant":
            channel_history[-1] = {
                "role": "assistant",
                "name": self.bot.character_name,
                "content": response,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        else:
            channel_history.append({
                "role": "assistant",
                "name": self.bot.character_name,
                "content": response,
                "timestamp": datetime.datetime.now().isoformat(),
            })
        
        self.bot._save_conversation(channel_id, channel_history)
        
        guild_id = context.user_discord_id.split(":")[0] if ":" in context.user_discord_id else "global"
        if hasattr(self.bot, 'memory_manager'):
            asyncio.create_task(self.bot.memory_manager.update_memory_from_conversation(
                context.user_name, context.user_message, response, guild_id
            ))
    
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User) -> None:
        if user.id == self.bot.user.id:
            return
            
        message_id = reaction.message.id
        message_group = None
        
        if self.bot._is_multipart_message(message_id):
            message_group = self.bot._get_message_group(message_id)
        
        if (reaction.emoji == "🗑️" and 
            reaction.message.author == self.bot.user and 
            (str(user.id) == self.bot.config_manager.get("owner_id") or
             (hasattr(reaction.message, "reference") and 
              reaction.message.reference and 
              reaction.message.reference.resolved and 
              user.id == reaction.message.reference.resolved.author.id))):
            await self.handle_delete_reaction(reaction, message_group)
            
        elif (reaction.emoji == "♻️" and reaction.message.author == self.bot.user):
            is_original_author = (
                hasattr(reaction.message, "reference") and
                reaction.message.reference and
                reaction.message.reference.resolved and
                user.id == reaction.message.reference.resolved.author.id
            )
            
            already_regenerated = any(r.emoji == "🔄" and r.me for r in reaction.message.reactions)
            
            if is_original_author and not already_regenerated:
                await self.handle_regenerate_reaction(reaction, message_group, message_id)

class OOCCommandHandler:
    def __init__(self, bot: Any):
        self.bot = bot
        
    async def _handle_regex_command(self, message: discord.Message, args: str) -> None:
        if not args:
            help_text = "**RegEx Commands:**\n"
            help_text += "- `//regex list` - List all regex scripts\n"
            help_text += "- `//regex test <script_name> <text>` - Test a regex script on text\n"
            help_text += "- `//regex toggle <script_name>` - Enable/disable a script\n"
            help_text += "- `//regex info <script_name>` - Show detailed info about a script\n"
            await message.reply(help_text)
            return
            
        subparts = args.split(" ", 1)
        subcommand = subparts[0].lower() if subparts else ""
        subargs = subparts[1] if len(subparts) > 1 else ""
        
        if subcommand == "list":
            scripts = self.bot.regex_manager.scripts
            
            embed = discord.Embed(title="RegEx Scripts")
            
            if scripts:
                scripts_text = ""
                for i, script in enumerate(scripts, 1):
                    status = "✅" if not script.disabled else "❌"
                    scripts_text += f"{i}. {status} **{script.name}**\n"
                embed.add_field(name="Scripts", value=scripts_text, inline=False)
            else:
                embed.add_field(name="Scripts", value="No scripts", inline=False)
                
            await message.reply(embed=embed)
            
        elif subcommand == "test" and subargs:
            test_parts = subargs.split(" ", 1)
            if len(test_parts) != 2:
                await message.reply("Format: //regex test <script_name> <text>")
                return
                
            script_name, test_text = test_parts
            
            script = self.bot.regex_manager.get_script(script_name, self.bot.character_name)
            
            if not script:
                await message.reply(f"Script '{script_name}' not found.")
                return
                
            result = script.apply(test_text)
            
            embed = discord.Embed(title=f"RegEx Test: {script.name}")
            embed.add_field(name="Input", value=test_text[:1024], inline=False)
            embed.add_field(name="Output", value=result[:1024], inline=False)
            
            if test_text == result:
                embed.set_footer(text="⚠️ No changes were made")
                embed.color = discord.Color.yellow()
            else:
                embed.set_footer(text="✅ Text was transformed")
                embed.color = discord.Color.green()
                
            await message.reply(embed=embed)
            
        elif subcommand == "toggle" and subargs:
            script_name = subargs.strip()
            script = self.bot.regex_manager.get_script(script_name)
            
            if not script:
                await message.reply(f"Script '{script_name}' not found.")
                return
                
            script.disabled = not script.disabled
            
            self.bot.regex_manager.save_scripts()
                
            status = "disabled" if script.disabled else "enabled"
            await message.reply(f"Script '{script_name}' is now {status}.")
            
        elif subcommand == "info" and subargs:
            script_name = subargs.strip()
            script = self.bot.regex_manager.get_script(script_name)
            
            if not script:
                await message.reply(f"Script '{script_name}' not found.")
                return
                
            embed = discord.Embed(title=f"RegEx Script: {script.name}")
            embed.add_field(name="Pattern", value=f"`{script.find_pattern}`", inline=False)
            embed.add_field(name="Replace With", value=f"`{script.replace_with}`", inline=False)
            
            if script.trim_out:
                embed.add_field(name="Trim Out", value=f"`{script.trim_out}`", inline=False)
                
            affects = []
            if script.affects_user_input:
                affects.append("User Input")
            if script.affects_ai_response:
                affects.append("AI Response")
            if script.affects_slash_commands:
                affects.append("Slash Commands")
            if script.affects_world_info: 
                affects.append("World Info")
            if script.affects_reasoning:
                affects.append("Reasoning")
            
            embed.add_field(name="Affects", value=", ".join(affects) if affects else "None", inline=False)
            embed.add_field(name="Status", value="Enabled" if not script.disabled else "Disabled", inline=False)
            
            await message.reply(embed=embed)
        else:
            await message.reply(f"Unknown regex subcommand: {subcommand}")
    
    async def _handle_memory_command(self, message: discord.Message, args: str, guild_id: str) -> None:
        if not hasattr(self.bot, 'memory_manager'):
            await message.reply("Memory system is not available.")
            return
            
        if args.lower() == "show":
            memory_display = self.bot.memory_manager.format_memories_for_display(guild_id)
        
            if len(memory_display) > 1900:
                chunks = []
                current_chunk = "**Character Memories:**\n"
                
                memory_entries = memory_display.split("\n")
                
                for entry in memory_entries:
                    if not entry.strip():
                        continue
                        
                    if len(current_chunk) + len(entry) + 1 > 1900:
                        chunks.append(current_chunk)
                        current_chunk = f"**Character Memories (continued):**\n{entry}\n"
                    else:
                        current_chunk += f"{entry}\n"
                
                if current_chunk.strip() != "**Character Memories (continued):**":
                    chunks.append(current_chunk)
                
                for i, chunk in enumerate(chunks):
                    await message.reply(chunk)
            else:
                await message.reply(memory_display)
        elif args.lower().startswith("search "):
            parts = args.split(" ", 1)
            if len(parts) > 1:
                search_term = parts[1]
                relevant_memories = self.bot.memory_manager.search_memory(search_term, guild_id)
                
                if relevant_memories:
                    memory_display = f"**Memories matching '{search_term}':**\n"
                    for memory in relevant_memories:
                        memory_display += f"{memory}\n"
                    
                    if len(memory_display) > 1900:
                        chunks = []
                        current_chunk = memory_display[:memory_display.find('\n')+1]
                        
                        memory_entries = memory_display[memory_display.find('\n')+1:].split("\n")
                        
                        for entry in memory_entries:
                            if not entry.strip():
                                continue
                                
                            if len(current_chunk) + len(entry) + 1 > 1900:
                                chunks.append(current_chunk)
                                current_chunk = f"**Memories matching '{search_term}' (continued):**\n{entry}\n"
                            else:
                                current_chunk += f"{entry}\n"
                        
                        if current_chunk.strip() != f"**Memories matching '{search_term}' (continued):**":
                            chunks.append(current_chunk)
                        
                        for chunk in chunks:
                            await message.reply(chunk)
                    else:
                        await message.reply(memory_display)
        elif args.lower().startswith("add "):
            mem_parts = args[4:].split(":", 1)
            if len(mem_parts) == 2:
                topic, details = mem_parts
                self.bot.memory_manager.add_memory(topic.strip(), details.strip(), message.author.display_name, guild_id)
                await message.reply(f"Added memory: {topic.strip()} (from {message.author.display_name})")
            else:
                await message.reply(
                    "Invalid format. Use: //memory add Topic: Details"
                )
        elif args.lower().startswith("remove "):
            topic = args[7:].strip()
            if self.bot.memory_manager.remove_memory(topic, guild_id):
                await message.reply(f"Removed memory: {topic}")
            else:
                await message.reply(f"Memory topic '{topic}' not found.")
        elif args.lower() == "clear":
            self.bot.memory_manager.clear_memories(guild_id)
            await message.reply("All memories cleared.")
            
    async def _handle_lore_command(self, message: discord.Message, args: str) -> None:
        if not hasattr(self.bot, 'lorebook_manager'):
            await message.reply("Lorebook system is not available.")
            return
            
        subparts = args.split(" ", 1)
        subcommand = subparts[0].lower() if subparts else ""
        subargs = subparts[1] if len(subparts) > 1 else ""

        if subcommand == "add" and subargs:
            lore_parts = subargs.split(":", 1)
            if len(lore_parts) == 2:
                keyword, content = lore_parts
                self.bot.lorebook_manager.add_entry(keyword.strip(), content.strip())
                await message.reply(
                    f"Added lorebook entry for keyword: {keyword.strip()}"
                )
            else:
                await message.reply(
                    "Invalid format. Use: //lore add Keyword: Content"
                )
        elif subcommand == "list":
            lore_display = self.bot.lorebook_manager.format_entries_for_display()
            await message.reply(lore_display)
        elif subcommand == "remove" and subargs:
            try:
                index = int(subargs) - 1
                if self.bot.lorebook_manager.remove_entry(index):
                    await message.reply(
                        f"Removed lorebook entry #{index+1}"
                    )
                else:
                    await message.reply("Invalid entry number.")
            except ValueError:
                await message.reply("Please provide a valid entry number.")
        elif subcommand == "clear":
            self.bot.lorebook_manager.clear_entries()
            await message.reply("All lorebook entries cleared.")
            
    async def _handle_activation_commands(self, message: discord.Message, command: str) -> None:
        if command == "activate":
            self.bot.activated_channels.add(message.channel.id)
            self.bot.config_manager_obj.save_config()
            await message.reply(
                f"{self.bot.character_name} will now respond to all messages in this channel."
            )
        elif command == "deactivate":
            if message.channel.id in self.bot.activated_channels:
                self.bot.activated_channels.remove(message.channel.id)
                self.bot.config_manager_obj.save_config()
            await message.reply(
                f"{self.bot.character_name} will now only respond when mentioned or called by name."
            )
            
    async def _handle_persona_command(self, message: discord.Message) -> None:
        persona_display = f"**{self.bot.character_name} Persona:**\n"
        persona_display += f"**Backstory:** {self.bot.character_backstory}\n"
        persona_display += f"**Appearance:** {self.bot.character_description}\n"
        persona_display += f"**Scenario:** {self.bot.character_scenario}\n"
        
        if self.bot.personality_age:
            persona_display += f"**Age:** {self.bot.personality_age}\n"
        if self.bot.personality_traits:
            persona_display += f"**Traits:** {self.bot.personality_traits}\n"
        if self.bot.personality_likes:
            persona_display += f"**Likes:** {self.bot.personality_likes}\n"
        if self.bot.personality_dislikes:
            persona_display += f"**Dislikes:** {self.bot.personality_dislikes}\n"
        if self.bot.personality_tone:
            persona_display += f"**Tone:** {self.bot.personality_tone}\n"
        if self.bot.personality_history:
            history_preview = self.bot.personality_history[:100] + "..." if len(self.bot.personality_history) > 100 else self.bot.personality_history
            persona_display += f"**History:** {history_preview}\n"
        if self.bot.personality_catchphrases:
            persona_display += f"**Catchphrases:** {self.bot.personality_catchphrases}\n"
        if self.bot.jailbreak:
            persona_display += f"**Presets:** {self.bot.jailbreak}\n"
        
        await message.reply(persona_display)
            
    async def _handle_save_command(self, message: discord.Message) -> None:
        self.bot.config_manager_obj.save_config()
        if hasattr(self.bot, 'memory_manager'):
            self.bot.memory_manager._save_memory()
        if hasattr(self.bot, 'lorebook_manager'):
            self.bot.lorebook_manager._save_lorebook()
        await message.reply("All data and settings saved!")
        
    async def _handle_help_command(self, message: discord.Message) -> None:
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
                
    async def _handle_ooc_command(self, message: discord.Message) -> None:
        clean_content = message.content.replace("//", "").replace("/ooc", "").strip()
        parts = clean_content.split(" ", 1)
        command = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        guild_id = str(message.guild.id) if message.guild else "global"

        if command == "regex" and hasattr(self.bot, 'regex_manager'):
            await self._handle_regex_command(message, args)
        elif command == "memory" or command == "wack":
            await self._handle_memory_command(message, args, guild_id)
        elif command == "lore":
            await self._handle_lore_command(message, args)
        elif command == "activate" or command == "deactivate":
            await self._handle_activation_commands(message, command)
        elif command == "persona":
            await self._handle_persona_command(message)
        elif command == "save":
            await self._handle_save_command(message)
        elif command == "help":
            await self._handle_help_command(message)
        else:
            await message.reply(f"Unknown command: {command}. Type //help for available commands.")
