import discord
import re
import os
import datetime
import asyncio
import logging

logger = logging.getLogger("openshape")

async def on_message(self, message: discord.Message):
    if message.author == self.user:
        return

    await self.process_commands(message)

    if message.author.id in self.blacklisted_users:
        return

    should_respond = False
    is_priority = False

    if self.always_reply_mentions and self.user in message.mentions:
        should_respond = True
        is_priority = True
    elif (hasattr(message, 'reference') and 
        message.reference and 
        message.reference.resolved and 
        message.reference.resolved.author.id == self.user.id):
        should_respond = True
        is_priority = True
    elif (
        self.reply_to_name
        and self.character_name.lower() in message.content.lower()
    ):
        should_respond = True
        is_priority = True
    elif message.channel.id in self.activated_channels:
        current_time = datetime.datetime.now().timestamp()
        last_time = self.channel_last_message_time.get(message.channel.id, 0)
        time_since_last_message = current_time - last_time
        
        if time_since_last_message >= self.message_cooldown_seconds:
            should_respond = True
            self.channel_last_message_time[message.channel.id] = current_time

    is_ooc = message.content.startswith("//") or message.content.startswith("/ooc")
    if is_ooc and message.author.id == self.owner_id:
        await self._handle_ooc_command(message)
        return

    if is_priority and message.channel.id in self.activated_channels:
        self.channel_last_message_time[message.channel.id] = datetime.datetime.now().timestamp()
    
    processed_content = message.content
    if hasattr(self, 'regex_manager'):
        macros = {
            "user": message.author.display_name,
            "char": self.character_name,
            "server": message.guild.name if message.guild else "DM",
            "channel": message.channel.name if hasattr(message.channel, 'name') else "DM"
        }
        
        processed_content = self.regex_manager.process_text(
            processed_content, 
            "user_input", 
            macros=macros
        )

    if should_respond:
        async with message.channel.typing():
            guild_id = str(message.guild.id) if message.guild else "global"
            clean_content = ""
            file_content = await self.file_parser.process_attachments(message)
            if file_content:
                logger.info('File content found')
                clean_content += f"\n\n{file_content}"
            clean_content += re.sub(r"<@!?(\d+)>", "", message.content).strip()

            channel_history = self.helpers.get_channel_conversation(message.channel.id)
            
            channel_history.append(
                {
                    "role": "user",
                    "name": message.author.display_name,
                    "content": clean_content,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "discord_id": str(message.author.id),
                }
            )
         
            if len(channel_history) > 8:
                channel_history = channel_history[-8:]

            relevant_lore = []
            if hasattr(self, 'lorebook_manager'):
                relevant_lore = self.lorebook_manager.get_relevant_entries(clean_content)
            
            relevant_memories = []
            if hasattr(self, 'memory_manager'):
                relevant_memories = self.memory_manager.search_memory(clean_content, guild_id)
            
            relevant_info = []
            if relevant_lore:
                relevant_info.extend(relevant_lore)
            if relevant_memories:
                relevant_info.extend(relevant_memories)

            response = ""
            if hasattr(self, 'api_client') and self.api_client:
                try:
                    messages = [
                        {"role": "system", "content": self.system_prompt}
                    ]
                    
                    if relevant_info:
                        info_text = "Relevant information:\n" + "\n".join(relevant_info)
                        messages.append({"role": "system", "content": info_text})
                    
                    for msg in channel_history:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
                    
                    completion = await self.ai_client.chat.completions.create(
                        model=self.chat_model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=1000,
                    )
                    
                    response = completion.choices[0].message.content
                except Exception as e:
                    logger.error(f"Error generating response: {e}")
                    response = "I apologize, but I'm having trouble responding right now. Please try again later."
            else:
                response = "I apologize, but my AI client is not configured correctly. Please ask my owner to set up API settings."
            
            if hasattr(self, 'regex_manager'):
                response = self.regex_manager.process_text(
                    response, 
                    "ai_response", 
                    macros=macros
                )

            channel_history.append(
                {
                    "role": "assistant",
                    "name": self.character_name,
                    "content": response,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "discord_id": str(self.user.id),
                }
            )
            
            if len(channel_history) > 8:
                channel_history = channel_history[-8:]

            if hasattr(self, 'memory_manager'):
                await self.memory_manager.update_memory_from_conversation(
                    message.author.display_name, clean_content, response, guild_id
                )

            self.helpers.save_conversation(message.channel.id, channel_history)

            formatted_response = (
                f"**{self.character_name}**: {response}"
                if self.add_character_name
                else response
            )
            
            if (self.use_tts and 
                hasattr(self, 'tts_handler') and 
                message.guild and 
                message.author.voice and 
                message.author.voice.channel):
                try:
                    temp_audio_file = await self.tts_handler.generate_temp_tts(response)
                    if temp_audio_file:
                        voice_channel = message.author.voice.channel

                        voice_client = message.guild.voice_client
                        if voice_client:
                            if voice_client.channel != voice_channel:
                                await voice_client.move_to(voice_channel)
                        else:
                            voice_client = await voice_channel.connect()

                        def after_playing(error):
                            try:
                                os.remove(temp_audio_file)
                                logger.info(f"Deleted temporary TTS file: {temp_audio_file}")
                            except Exception as e:
                                logger.error(f"Error deleting temporary TTS file: {e}")
                            
                            asyncio.run_coroutine_threadsafe(
                                self.tts_handler.disconnect_after_audio(voice_client),
                                self.loop,
                            )

                        voice_client.play(
                            discord.FFmpegPCMAudio(temp_audio_file),
                            after=after_playing,
                        )
                except Exception as e:
                    logger.error(f"Error playing TTS audio: {e}")
            
            sent_message, message_group = await self.helpers.send_long_message(
                message.channel,
                formatted_response,
                reference=message,
                reply=True
            )

            await sent_message.add_reaction("🗑️")
            await sent_message.add_reaction("♻️")

            context = {
                "user_name": message.author.display_name,
                "user_message": clean_content,
                "channel_history": channel_history[:-1],
                "relevant_info": relevant_info,
                "original_message": message.id,
                "user_discord_id": str(message.author.id),
            }
            
            primary_id = message_group["primary_id"]
            if primary_id:
                self.helpers.save_message_context(primary_id, context)


async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
    if user.id == self.user.id:
        return
        
    message_id = reaction.message.id
    message_group = None
    
    if self.helpers.is_multipart_message(message_id):
        message_group = self.helpers.get_message_group(message_id)
    
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
        if message_group and message_group["is_multipart"]:
            for msg_id in message_group["message_ids"]:
                try:
                    msg = await reaction.message.channel.fetch_message(msg_id)
                    await msg.delete()
                except (discord.NotFound, discord.HTTPException):
                    continue
        else:
            await reaction.message.delete()
        
    elif (
        reaction.emoji == "♻️"
        and reaction.message.author == self.user
    ):
        is_original_author = (
            hasattr(reaction.message, "reference")
            and reaction.message.reference
            and reaction.message.reference.resolved
            and user.id == reaction.message.reference.resolved.author.id
        )
        
        already_regenerated = any(r.emoji == "🔄" and r.me for r in reaction.message.reactions)
        
        if is_original_author and not already_regenerated:
            context_message_id = message_id
            if message_group and message_group["primary_id"]:
                context_message_id = message_group["primary_id"]
                
            context = self.helpers.get_message_context(context_message_id)
            
            if context:
                async with reaction.message.channel.typing():
                    response = ""
                    if hasattr(self, 'api_client') and self.api_client:
                        try:
                            messages = [
                                {"role": "system", "content": self.system_prompt}
                            ]
                            
                            if context["relevant_info"]:
                                info_text = "Relevant information:\n" + "\n".join(context["relevant_info"])
                                messages.append({"role": "system", "content": info_text})
                            
                            for msg in context["channel_history"]:
                                messages.append({
                                    "role": msg["role"],
                                    "content": msg["content"]
                                })
                            
                            messages.append({
                                "role": "user",
                                "content": context["user_message"]
                            })
                            
                            completion = await self.ai_client.chat.completions.create(
                                model=self.chat_model,
                                messages=messages,
                                temperature=0.7,
                                max_tokens=1000,
                            )
                            
                            response = completion.choices[0].message.content
                        except Exception as e:
                            logger.error(f"Error regenerating response: {e}")
                            response = "I apologize, but I'm having trouble responding right now. Please try again later."
                    else:
                        response = "I apologize, but my AI client is not configured correctly. Please ask my owner to set up API settings."
                    
                    if hasattr(self, 'regex_manager'):
                        macros = {
                            "user": context["user_name"],
                            "char": self.character_name,
                            "server": reaction.message.guild.name if reaction.message.guild else "DM",
                            "channel": reaction.message.channel.name if hasattr(reaction.message.channel, 'name') else "DM"
                        }
                        
                        response = self.regex_manager.process_text(
                            response, 
                            "ai_response", 
                            macros=macros
                        )
                    
                    formatted_response = (
                        f"**{self.character_name}**: {response}"
                        if self.add_character_name
                        else response
                    )
                    
                    if message_group and message_group["is_multipart"]:
                        for msg_id in message_group["message_ids"]:
                            try:
                                msg = await reaction.message.channel.fetch_message(msg_id)
                                await msg.delete()
                            except (discord.NotFound, discord.HTTPException):
                                continue
                        
                        try:
                            original_message = await reaction.message.channel.fetch_message(context["original_message"])
                            
                            primary_message, new_message_group = await self.helpers.send_long_message(
                                reaction.message.channel, 
                                formatted_response,
                                reference=original_message
                            )
                            
                            await primary_message.add_reaction("🗑️")
                            await primary_message.add_reaction("🔄")
                            
                            self.helpers.save_message_context(primary_message.id, context)
                            
                        except (discord.NotFound, discord.HTTPException):
                            primary_message, new_message_group = await self.helpers.send_long_message(
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
                                original_message = await reaction.message.channel.fetch_message(context["original_message"])
                                
                                primary_message, new_message_group = await self.helpers.send_long_message(
                                    reaction.message.channel, 
                                    formatted_response,
                                    reference=original_message
                                )
                                
                                await primary_message.add_reaction("🗑️")
                                await primary_message.add_reaction("🔄")
                                
                                self.helpers.save_message_context(primary_message.id, context)
                                
                            except (discord.NotFound, discord.HTTPException):
                                primary_message, new_message_group = await self.helpers.send_long_message(
                                    reaction.message.channel, 
                                    formatted_response
                                )
                                await primary_message.add_reaction("🗑️")
                    
                    channel_history = self.helpers.get_channel_conversation(reaction.message.channel.id)
                    
                    if channel_history and channel_history[-1]["role"] == "assistant":
                        channel_history[-1] = {
                            "role": "assistant",
                            "name": self.character_name,
                            "content": response,
                            "timestamp": datetime.datetime.now().isoformat(),
                        }
                    else:
                        channel_history.append({
                            "role": "assistant",
                            "name": self.character_name,
                            "content": response,
                            "timestamp": datetime.datetime.now().isoformat(),
                        })
                    
                    self.helpers.save_conversation(reaction.message.channel.id, channel_history)
                    
                    if hasattr(self, 'memory_manager'):
                        guild_id = str(reaction.message.guild.id) if reaction.message.guild else "global"
                        await self.memory_manager.update_memory_from_conversation(
                            context["user_name"], context["user_message"], response, guild_id
                        )

async def _handle_ooc_command(self, message: discord.Message):
    clean_content = message.content.replace("//", "").replace("/ooc", "").strip()
    parts = clean_content.split(" ", 1)
    command = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""
    guild_id = str(message.guild.id) if message.guild else "global"

    if command == "regex":
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
            scripts = self.regex_manager.scripts
            
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
            
            script = self.regex_manager.get_script(script_name, self.character_name)
            
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
            script = self.regex_manager.get_script(script_name)
            
            if not script:
                await message.reply(f"Script '{script_name}' not found.")
                return
                
            script.disabled = not script.disabled
            
            self.regex_manager.save_scripts()
                
            status = "disabled" if script.disabled else "enabled"
            await message.reply(f"Script '{script_name}' is now {status}.")
            
        elif subcommand == "info" and subargs:
            script_name = subargs.strip()
            script = self.regex_manager.get_script(script_name)
            
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
            
    elif command == "memory" or command == "wack":
        if not hasattr(self, 'memory_manager'):
            await message.reply("Memory system is not available.")
            return
            
        if args.lower() == "show":
            memory_display = self.memory_manager.format_memories_for_display(guild_id)
        
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
        elif args.lower().startswith("search ") and len(parts) > 2:
            search_term = parts[2]
            relevant_memories = self.memory_manager.search_memory(search_term, guild_id)
            
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
                self.memory_manager.add_memory(topic.strip(), details.strip(), message.author.display_name, guild_id)
                await message.reply(f"Added memory: {topic.strip()} (from {message.author.display_name})")
            else:
                await message.reply(
                    "Invalid format. Use: //memory add Topic: Details"
                )
        elif args.lower().startswith("remove "):
            topic = args[7:].strip()
            if self.memory_manager.remove_memory(topic, guild_id):
                await message.reply(f"Removed memory: {topic}")
            else:
                await message.reply(f"Memory topic '{topic}' not found.")
        elif args.lower() == "clear" or command == "wack":
            self.memory_manager.clear_memories(guild_id)
            await message.reply("All memories cleared.")
    elif command == "lore":
        if not hasattr(self, 'lorebook_manager'):
            await message.reply("Lorebook system is not available.")
            return
            
        subparts = args.split(" ", 1)
        subcommand = subparts[0].lower() if subparts else ""
        subargs = subparts[1] if len(subparts) > 1 else ""

        if subcommand == "add" and subargs:
            lore_parts = subargs.split(":", 1)
            if len(lore_parts) == 2:
                keyword, content = lore_parts
                self.lorebook_manager.add_entry(keyword.strip(), content.strip())
                await message.reply(
                    f"Added lorebook entry for keyword: {keyword.strip()}"
                )
            else:
                await message.reply(
                    "Invalid format. Use: //lore add Keyword: Content"
                )
        elif subcommand == "list":
            lore_display = self.lorebook_manager.format_entries_for_display()
            await message.reply(lore_display)
        elif subcommand == "remove" and subargs:
            try:
                index = int(subargs) - 1
                if self.lorebook_manager.remove_entry(index):
                    await message.reply(
                        f"Removed lorebook entry #{index+1}"
                    )
                else:
                    await message.reply("Invalid entry number.")
            except ValueError:
                await message.reply("Please provide a valid entry number.")
        elif subcommand == "clear":
            self.lorebook_manager.clear_entries()
            await message.reply("All lorebook entries cleared.")

    elif command == "activate":
        self.activated_channels.add(message.channel.id)
        self.config_manager.save_config()
        await message.reply(
            f"{self.character_name} will now respond to all messages in this channel."
        )

    elif command == "deactivate":
        if message.channel.id in self.activated_channels:
            self.activated_channels.remove(message.channel.id)
            self.config_manager.save_config()
        await message.reply(
            f"{self.character_name} will now only respond when mentioned or called by name."
        )

    elif command == "persona":
        persona_display = f"**{self.character_name} Persona:**\n"
        persona_display += f"**Backstory:** {self.character_backstory}\n"
        persona_display += f"**Appearance:** {self.character_description}\n"
        persona_display += f"**Scenario:** {self.character_scenario}\n"
        
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
        if self.jailbreak:
            persona_display += f"**Presets:** {self.jailbreak}\n"
        
        await message.reply(persona_display)

    elif command == "save":
        self.config_manager.save_config()
        if hasattr(self, 'memory_manager'):
            self.memory_manager._save_memory()
        if hasattr(self, 'lorebook_manager'):
            self.lorebook_manager._save_lorebook()
        await message.reply("All data and settings saved!")

    elif command == "help":
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
