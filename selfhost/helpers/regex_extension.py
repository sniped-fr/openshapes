import discord, re, os, json, logging, asyncio, io
from discord.ext import commands
from typing import Dict, List, Optional, Pattern, Union

logger = logging.getLogger("openshape.regex_extension")

class RegexScript:
    def __init__(
        self,
        name: str,
        find_pattern: str,
        replace_with: str,
        trim_out: str = "",
        affects_user_input: bool = False,
        affects_ai_response: bool = False,
        affects_slash_commands: bool = False,
        affects_world_info: bool = False,
        affects_reasoning: bool = False,
        run_on_edit: bool = True,
        macros_in_find: str = "escaped",
        min_depth: int = -1,
        max_depth: int = -1,
        disabled: bool = False,
        alter_display: bool = True,
        alter_outgoing_prompt: bool = True
    ):
        self.name = name
        self.find_pattern = find_pattern
        self.replace_with = replace_with
        self.trim_out = trim_out
        self.affects_user_input = affects_user_input
        self.affects_ai_response = affects_ai_response
        self.affects_slash_commands = affects_slash_commands
        self.affects_world_info = affects_world_info
        self.affects_reasoning = affects_reasoning
        self.run_on_edit = run_on_edit
        self.macros_in_find = macros_in_find  # "don't_substitute", "raw", or "escaped"
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.disabled = disabled
        self.alter_display = alter_display
        self.alter_outgoing_prompt = alter_outgoing_prompt
        
        # Compile the regex pattern if possible
        self._compiled_pattern: Optional[Pattern] = None
        self._compile_pattern()
        
    def _compile_pattern(self):
        """Compile the regex pattern with specified flags"""
        if not self.find_pattern:
            return
        
        pattern = self.find_pattern
        flags = 0
        
        # Check if pattern has flags specified in format /pattern/flags
        if pattern.startswith('/') and '/' in pattern[1:]:
            parts = pattern.split('/')
            if len(parts) >= 3:
                pattern = parts[1]
                flag_str = parts[2]
                
                # Process flags
                if 'i' in flag_str:
                    flags |= re.IGNORECASE
                if 's' in flag_str:
                    flags |= re.DOTALL
                if 'm' in flag_str:
                    flags |= re.MULTILINE
                if 'u' in flag_str:
                    flags |= re.UNICODE
        
        try:
            self._compiled_pattern = re.compile(pattern, flags)
        except re.error as e:
            logger.error(f"Failed to compile regex pattern '{pattern}': {e}")
            self._compiled_pattern = None

    def process_macros(self, text: str, macros: Dict[str, str]) -> str:
        """Replace macros in the text based on the configured macro handling"""
        if self.macros_in_find == "don't_substitute":
            return text
            
        for key, value in macros.items():
            macro_pattern = "{{" + key + "}}"
            if macro_pattern in text:
                if self.macros_in_find == "escaped":
                    # Escape special regex characters in the value
                    escaped_value = re.escape(value)
                    text = text.replace(macro_pattern, escaped_value)
                else:  # Raw
                    text = text.replace(macro_pattern, value)
                    
        return text

    def apply(self, text: str, macros: Dict[str, str] = None, depth: int = 0) -> str:
        """Apply the regex transformation to the text"""
        if self.disabled:
            return text
            
        # Check depth constraints
        if self.min_depth != -1 and depth < self.min_depth:
            return text
        if self.max_depth != -1 and depth > self.max_depth:
            return text
            
        if not text or not self.find_pattern:
            return text
            
        # Process any macros in the find pattern
        macros = macros or {}
        find_pattern = self.process_macros(self.find_pattern, macros)
        
        # Compile the pattern if needed
        if not self._compiled_pattern:
            try:
                self._compiled_pattern = re.compile(find_pattern)
            except re.error as e:
                logger.error(f"Failed to compile regex pattern '{find_pattern}': {e}")
                return text
        
        result = text
        
        # Handle trim out functionality
        trim_items = self.trim_out.strip().split('\n') if self.trim_out else []
        
        # Apply global flag by default if pattern uses /pattern/g format
        if self.find_pattern.startswith('/') and 'g' in self.find_pattern.split('/')[-1]:
            # For global replacement, we need to find all matches and replace each
            matches = list(self._compiled_pattern.finditer(text))
            
            # Process matches in reverse to not affect positions
            for match in reversed(matches):
                matched_text = match.group(0)
                trimmed_text = matched_text
                
                # Apply trims
                for trim in trim_items:
                    trimmed_text = trimmed_text.replace(trim, '')
                
                # Prepare replacement with capture groups
                replacement = self.replace_with
                
                # Replace {{match}} with the actual match (after trimming)
                replacement = replacement.replace("{{match}}", trimmed_text)
                
                # Replace capture group references
                for i, group in enumerate(match.groups(), 1):
                    if group:  # Only replace if the group matched something
                        replacement = replacement.replace(f"${i}", group)
                
                # Replace the match in the text
                result = result[:match.start()] + replacement + result[match.end():]
                
        else:
            # Single replacement
            match = self._compiled_pattern.search(text)
            if match:
                matched_text = match.group(0)
                trimmed_text = matched_text
                
                # Apply trims
                for trim in trim_items:
                    trimmed_text = trimmed_text.replace(trim, '')
                
                # Prepare replacement with capture groups
                replacement = self.replace_with
                
                # Replace {{match}} with the actual match (after trimming)
                replacement = replacement.replace("{{match}}", trimmed_text)
                
                # Replace capture group references
                for i, group in enumerate(match.groups(), 1):
                    if group:  # Only replace if the group matched something
                        replacement = replacement.replace(f"${i}", group)
                
                # Replace the match in the text
                result = result[:match.start()] + replacement + result[match.end():]
        
        return result
        
    def to_dict(self) -> Dict:
        """Convert the script to a dictionary for serialization"""
        return {
            "name": self.name,
            "find_pattern": self.find_pattern,
            "replace_with": self.replace_with,
            "trim_out": self.trim_out,
            "affects_user_input": self.affects_user_input,
            "affects_ai_response": self.affects_ai_response,
            "affects_slash_commands": self.affects_slash_commands,
            "affects_world_info": self.affects_world_info,
            "affects_reasoning": self.affects_reasoning,
            "run_on_edit": self.run_on_edit,
            "macros_in_find": self.macros_in_find,
            "min_depth": self.min_depth,
            "max_depth": self.max_depth,
            "disabled": self.disabled,
            "alter_display": self.alter_display,
            "alter_outgoing_prompt": self.alter_outgoing_prompt
        }
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'RegexScript':
        """Create a RegexScript from a dictionary"""
        return cls(
            name=data.get("name", "Unnamed Script"),
            find_pattern=data.get("find_pattern", ""),
            replace_with=data.get("replace_with", ""),
            trim_out=data.get("trim_out", ""),
            affects_user_input=data.get("affects_user_input", False),
            affects_ai_response=data.get("affects_ai_response", False),
            affects_slash_commands=data.get("affects_slash_commands", False),
            affects_world_info=data.get("affects_world_info", False),
            affects_reasoning=data.get("affects_reasoning", False),
            run_on_edit=data.get("run_on_edit", True),
            macros_in_find=data.get("macros_in_find", "escaped"),
            min_depth=data.get("min_depth", -1),
            max_depth=data.get("max_depth", -1),
            disabled=data.get("disabled", False),
            alter_display=data.get("alter_display", True),
            alter_outgoing_prompt=data.get("alter_outgoing_prompt", True)
        )

class RegexManager:
    def __init__(self, bot):
        self.bot = bot
        self.scripts: List[RegexScript] = []
        self.scripts_path = os.path.join(self.bot.data_dir, "regex_scripts.json")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.scripts_path), exist_ok=True)
        
        # Load scripts
        self.load_scripts()
        
    def load_scripts(self):
        """Load RegEx scripts from file"""
        if os.path.exists(self.scripts_path):
            try:
                with open(self.scripts_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.scripts = [RegexScript.from_dict(script_data) 
                                   for script_data in data]
                logger.info(f"Loaded {len(self.scripts)} RegEx scripts")
            except Exception as e:
                logger.error(f"Failed to load RegEx scripts: {e}")
                self.scripts = []
        else:
            self.scripts = []
            
    def save_scripts(self):
        """Save RegEx scripts to file"""
        try:
            with open(self.scripts_path, 'w', encoding='utf-8') as f:
                json.dump([script.to_dict() for script in self.scripts], f, indent=2)
            logger.info(f"Saved {len(self.scripts)} RegEx scripts")
        except Exception as e:
            logger.error(f"Failed to save RegEx scripts: {e}")
            
    def add_script(self, script: RegexScript):
        """Add a new RegEx script"""
        self.scripts.append(script)
        self.save_scripts()
            
    def remove_script(self, script_name: str):
        """Remove a RegEx script by name"""
        self.scripts = [s for s in self.scripts if s.name != script_name]
        self.save_scripts()
                
    def get_script(self, script_name: str) -> Optional[RegexScript]:
        """Get a RegEx script by name"""
        for script in self.scripts:
            if script.name == script_name:
                return script
        return None
        
    def process_text(self, text: str, text_type: str, macros: Dict[str, str] = None, depth: int = 0) -> str:
        """
        Process text through applicable RegEx scripts
        
        Args:
            text: The text to process
            text_type: Type of text ("user_input", "ai_response", "slash_command", "world_info", "reasoning")
            macros: Dictionary of macros to substitute in find patterns
            depth: Depth of the message in the conversation history
            
        Returns:
            Processed text
        """
        if not text:
            return text
            
        result = text
        applied_scripts = []
        
        # Apply scripts based on text type
        for script in self.scripts:
            if script.disabled:
                continue
                
            should_apply = False
            
            # Check if script should be applied based on text type
            if text_type == "user_input" and script.affects_user_input:
                should_apply = True
            elif text_type == "ai_response" and script.affects_ai_response:
                should_apply = True
            elif text_type == "slash_command" and script.affects_slash_commands:
                should_apply = True
            elif text_type == "world_info" and script.affects_world_info:
                should_apply = True
            elif text_type == "reasoning" and script.affects_reasoning:
                should_apply = True
                
            if should_apply:
                original = result
                result = script.apply(result, macros, depth)
                if original != result:
                    applied_scripts.append(script.name)
                    
        if applied_scripts:
            logger.debug(f"Applied RegEx scripts to {text_type}: {', '.join(applied_scripts)}")
            
        return result

class RegexCreateModal(discord.ui.Modal):
    def __init__(self, manager, edit_script=None):
        title = "Edit RegEx Script" if edit_script else "Create RegEx Script"
        super().__init__(title=title)
        self.manager = manager
        self.edit_script = edit_script
        
        # Add fields
        self.name_input = discord.ui.TextInput(
            label="Script Name",
            placeholder="Enter a name for this script",
            max_length=50,
            required=True,
            default=edit_script.name if edit_script else ""
        )
        self.add_item(self.name_input)
        
        self.pattern_input = discord.ui.TextInput(
            label="Find RegEx Pattern",
            placeholder="Regular expression to match",
            style=discord.TextStyle.paragraph,
            required=True,
            default=edit_script.find_pattern if edit_script else ""
        )
        self.add_item(self.pattern_input)
        
        self.replace_input = discord.ui.TextInput(
            label="Replace With",
            placeholder="Replacement text (use {{match}} for matched text)",
            style=discord.TextStyle.paragraph,
            required=True,
            default=edit_script.replace_with if edit_script else ""
        )
        self.add_item(self.replace_input)
        
        self.trim_input = discord.ui.TextInput(
            label="Trim Out (optional)",
            placeholder="Text to remove from match (one per line)",
            style=discord.TextStyle.paragraph,
            required=False,
            default=edit_script.trim_out if edit_script else ""
        )
        self.add_item(self.trim_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        # Create or update the script with basic info
        if self.edit_script:
            script = self.edit_script
            script.name = self.name_input.value
            script.find_pattern = self.pattern_input.value
            script.replace_with = self.replace_input.value
            script.trim_out = self.trim_input.value
        else:
            script = RegexScript(
                name=self.name_input.value,
                find_pattern=self.pattern_input.value,
                replace_with=self.replace_input.value,
                trim_out=self.trim_input.value,
            )
        
        # Show settings view to configure rest of options
        settings_view = RegexSettingsView(self.manager, script, self.edit_script is not None)
        await interaction.response.send_message(
            "Configure when this RegEx script should be applied:", 
            view=settings_view, 
            ephemeral=True
        )

class RegexSettingsView(discord.ui.View):
    def __init__(self, manager, script, is_edit=False):
        super().__init__(timeout=300)
        self.manager = manager
        self.script = script
        self.is_edit = is_edit
        
        # Add options as buttons/selects to the view
        
    @discord.ui.select(
        placeholder="Affects which text?",
        min_values=0,
        max_values=5,
        options=[
            discord.SelectOption(label="User Input", description="Apply to user messages", value="user_input"),
            discord.SelectOption(label="AI Response", description="Apply to AI responses", value="ai_response"),
            discord.SelectOption(label="Slash Commands", description="Apply to slash command outputs", value="slash_cmds"),
            discord.SelectOption(label="World Info", description="Apply to world info entries", value="world_info"),
            discord.SelectOption(label="Reasoning", description="Apply to AI reasoning blocks", value="reasoning"),
        ]
    )
    async def affects_select(self, interaction: discord.Interaction, select):
        # Update script settings
        self.script.affects_user_input = "user_input" in select.values
        self.script.affects_ai_response = "ai_response" in select.values
        self.script.affects_slash_commands = "slash_cmds" in select.values
        self.script.affects_world_info = "world_info" in select.values
        self.script.affects_reasoning = "reasoning" in select.values
        await interaction.response.defer()
        
    @discord.ui.select(
        placeholder="Macro substitution in Find RegEx",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Don't Substitute", description="Don't replace macros in find pattern", value="don't_substitute"),
            discord.SelectOption(label="Raw Substitution", description="Raw replacement of macros", value="raw"),
            discord.SelectOption(label="Escaped Substitution", description="Escape special characters in macros", value="escaped"),
        ]
    )
    async def macro_select(self, interaction: discord.Interaction, select):
        self.script.macros_in_find = select.values[0]
        await interaction.response.defer()
        
    @discord.ui.button(label="Toggle Run On Edit", style=discord.ButtonStyle.secondary)
    async def toggle_run_on_edit(self, interaction: discord.Interaction, button):
        self.script.run_on_edit = not self.script.run_on_edit
        button.label = f"Run On Edit: {'✓' if self.script.run_on_edit else '✗'}"
        await interaction.response.edit_message(view=self)
        
    @discord.ui.button(label="Set Ephemerality", style=discord.ButtonStyle.secondary)
    async def set_ephemerality(self, interaction: discord.Interaction, button):
        # Create ephemeral settings modal
        modal = RegexEphemeralnessModal(self.script)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Set Depth Settings", style=discord.ButtonStyle.secondary)
    async def set_depth(self, interaction: discord.Interaction, button):
        modal = RegexDepthModal(self.script)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Test Script", style=discord.ButtonStyle.primary)
    async def test_script(self, interaction: discord.Interaction, button):
        modal = RegexTestModal(self.script)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Save", style=discord.ButtonStyle.success)
    async def save_script(self, interaction: discord.Interaction, button):
        if not self.is_edit:
            self.manager.add_script(self.script)
            await interaction.response.send_message(f"RegEx script '{self.script.name}' added.", ephemeral=True)
        else:
            self.manager.save_scripts()
            await interaction.response.send_message(f"RegEx script '{self.script.name}' updated.", ephemeral=True)

class RegexEphemeralnessModal(discord.ui.Modal):
    def __init__(self, script):
        super().__init__(title="Set RegEx Ephemerality")
        self.script = script
        
        # Explanation text
        self.add_item(discord.ui.TextInput(
            label="Ephemerality Settings",
            style=discord.TextStyle.paragraph,
            default="Select which changes should be applied:\n1 = Alter displayed text\n2 = Alter outgoing prompt\nLeave both checked to apply changes but not save them to chat file.",
            required=False
        ))
        
        # Display toggle
        self.display_toggle = discord.ui.TextInput(
            label="Alter Display",
            placeholder="1 for yes, 0 for no",
            default="1" if script.alter_display else "0",
            required=True,
            max_length=1
        )
        self.add_item(self.display_toggle)
        
        # Prompt toggle
        self.prompt_toggle = discord.ui.TextInput(
            label="Alter Outgoing Prompt",
            placeholder="1 for yes, 0 for no",
            default="1" if script.alter_outgoing_prompt else "0",
            required=True,
            max_length=1
        )
        self.add_item(self.prompt_toggle)
        
    async def on_submit(self, interaction: discord.Interaction):
        self.script.alter_display = self.display_toggle.value == "1"
        self.script.alter_outgoing_prompt = self.prompt_toggle.value == "1"
        await interaction.response.send_message(
            f"Ephemerality settings updated:\n"
            f"- Alter Display: {'✓' if self.script.alter_display else '✗'}\n"
            f"- Alter Outgoing Prompt: {'✓' if self.script.alter_outgoing_prompt else '✗'}",
            ephemeral=True
        )

class RegexDepthModal(discord.ui.Modal):
    def __init__(self, script):
        super().__init__(title="Set RegEx Depth Settings")
        self.script = script
        
        # Explanation text
        self.add_item(discord.ui.TextInput(
            label="Depth Settings",
            style=discord.TextStyle.paragraph,
            default="Control which messages in history are affected:\nMin Depth: Only affects messages at least N deep\nMax Depth: Only affects messages no deeper than N\nUse -1 for unlimited.",
            required=False
        ))
        
        # Min depth
        self.min_depth = discord.ui.TextInput(
            label="Minimum Depth (-1 for unlimited)",
            placeholder="Enter a number (-1 for unlimited)",
            default=str(script.min_depth),
            required=True
        )
        self.add_item(self.min_depth)
        
        # Max depth
        self.max_depth = discord.ui.TextInput(
            label="Maximum Depth (-1 for unlimited)",
            placeholder="Enter a number (-1 for unlimited)",
            default=str(script.max_depth),
            required=True
        )
        self.add_item(self.max_depth)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            min_depth = int(self.min_depth.value)
            max_depth = int(self.max_depth.value)
            
            self.script.min_depth = min_depth
            self.script.max_depth = max_depth
            
            await interaction.response.send_message(
                f"Depth settings updated:\n"
                f"- Min Depth: {min_depth if min_depth != -1 else 'Unlimited'}\n"
                f"- Max Depth: {max_depth if max_depth != -1 else 'Unlimited'}",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Invalid depth values. Please enter valid numbers.",
                ephemeral=True
            )

class RegexTestModal(discord.ui.Modal):
    def __init__(self, script):
        super().__init__(title="Test RegEx Script")
        self.script = script
        
        # Test input
        self.test_input = discord.ui.TextInput(
            label="Test Input",
            placeholder="Enter text to test the RegEx pattern on",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.test_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        input_text = self.test_input.value
        output_text = self.script.apply(input_text)
        
        embed = discord.Embed(title=f"RegEx Test: {self.script.name}")
        embed.add_field(name="Input", value=input_text[:1024] or "Empty input", inline=False)
        embed.add_field(name="Output", value=output_text[:1024] or "Empty output", inline=False)
        embed.add_field(name="Pattern", value=f"`{self.script.find_pattern}`", inline=False)
        embed.add_field(name="Replace", value=f"`{self.script.replace_with}`", inline=False)
        
        if input_text == output_text:
            embed.set_footer(text="⚠️ No changes were made to the input text")
            embed.color = discord.Color.yellow()
        else:
            embed.set_footer(text="✅ Text was successfully transformed")
            embed.color = discord.Color.green()
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RegexManagementView(discord.ui.View):
    def __init__(self, manager):
        super().__init__(timeout=300)
        self.manager = manager
        self.page = 0
        self.page_size = 10
        
    async def generate_embed(self, interaction):
        scripts = self.manager.scripts
        title = "RegEx Scripts"
            
        embed = discord.Embed(title=title)
        
        start_idx = self.page * self.page_size
        end_idx = min(start_idx + self.page_size, len(scripts))
        
        if scripts:
            for i, script in enumerate(scripts[start_idx:end_idx], start=start_idx + 1):
                status = "✅" if not script.disabled else "❌"
                affects = []
                if script.affects_user_input: affects.append("User")
                if script.affects_ai_response: affects.append("AI")
                if script.affects_slash_commands: affects.append("Commands")
                if script.affects_world_info: affects.append("WorldInfo")
                if script.affects_reasoning: affects.append("Reasoning")
                
                affects_str = ", ".join(affects) if affects else "None"
                
                embed.add_field(
                    name=f"{i}. {status} {script.name}",
                    value=f"Pattern: `{script.find_pattern[:30]}{'...' if len(script.find_pattern) > 30 else ''}`\n"
                          f"Affects: {affects_str}",
                    inline=False
                )
        else:
            embed.description = "No RegEx scripts found."
            
        # Add pagination info
        total_pages = max((len(scripts) + self.page_size - 1) // self.page_size, 1)
        embed.set_footer(text=f"Page {self.page + 1}/{total_pages}")
        
        return embed
        
    @discord.ui.button(label="Create Script", style=discord.ButtonStyle.primary)
    async def create_script(self, interaction: discord.Interaction, button):
        modal = RegexCreateModal(self.manager)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_script(self, interaction: discord.Interaction, button):
        # Create a modal to select which script to delete
        modal = discord.ui.Modal(title="Delete RegEx Script")
        
        script_select = discord.ui.TextInput(
            label="Script Number to Delete",
            placeholder="Enter the number from the list",
            required=True
        )
        modal.add_item(script_select)
        
        async def on_submit(modal_interaction):
            try:
                script_idx = int(script_select.value) - 1
                scripts = self.manager.scripts
                    
                if 0 <= script_idx < len(scripts):
                    script = scripts[script_idx]
                    
                    # Store a reference to the main view
                    main_view = self
                    
                    # Ask for confirmation
                    confirm_view = discord.ui.View(timeout=60)
                    
                    # Create proper button instances
                    confirm_button = discord.ui.Button(label="Confirm Delete", style=discord.ButtonStyle.danger)
                    cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
                    
                    # Define callback functions
                    async def confirm_callback(confirm_interaction):
                        try:
                            # Remove the script
                            main_view.manager.scripts.pop(script_idx)
                            main_view.manager.save_scripts()
                                
                            await confirm_interaction.response.send_message(f"Script '{script.name}' has been deleted.", ephemeral=True)
                            
                            # Update the embed on the original message
                            embed = await main_view.generate_embed(interaction)
                            await interaction.message.edit(embed=embed, view=main_view)
                        except Exception as e:
                            await confirm_interaction.response.send_message(f"Error deleting script: {str(e)}", ephemeral=True)
                    
                    async def cancel_callback(cancel_interaction):
                        await cancel_interaction.response.send_message("Deletion cancelled.", ephemeral=True)
                    
                    # Assign callbacks to buttons
                    confirm_button.callback = confirm_callback
                    cancel_button.callback = cancel_callback
                    
                    # Add buttons to view
                    confirm_view.add_item(confirm_button)
                    confirm_view.add_item(cancel_button)
                    
                    await modal_interaction.response.send_message(
                        f"Are you sure you want to delete the script '{script.name}'?", 
                        view=confirm_view,
                        ephemeral=True
                    )
                else:
                    await modal_interaction.response.send_message("Invalid script number.", ephemeral=True)
            except ValueError:
                await modal_interaction.response.send_message("Please enter a valid number.", ephemeral=True)
                
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary)
    async def edit_script(self, interaction: discord.Interaction, button):
        # Create a modal to select which script to edit
        modal = discord.ui.Modal(title="Edit RegEx Script")
        
        script_select = discord.ui.TextInput(
            label="Script Number to Edit",
            placeholder="Enter the number from the list",
            required=True
        )
        modal.add_item(script_select)
        
        async def on_submit(modal_interaction):
            try:
                script_idx = int(script_select.value) - 1
                scripts = self.manager.scripts
                    
                if 0 <= script_idx < len(scripts):
                    script = scripts[script_idx]
                    
                    # Create a proper view with buttons
                    view = discord.ui.View(timeout=60)
                    
                    # Create the edit button properly
                    edit_button = discord.ui.Button(label="Edit Script", style=discord.ButtonStyle.primary)
                    
                    async def edit_button_callback(button_interaction):
                        edit_modal = RegexCreateModal(
                            self.manager,
                            edit_script=script
                        )
                        await button_interaction.response.send_modal(edit_modal)
                    
                    # Assign the callback to the button
                    edit_button.callback = edit_button_callback
                    
                    # Add the button to the view
                    view.add_item(edit_button)
                    
                    await modal_interaction.response.send_message(
                        f"Click the button below to edit script '{script.name}':", 
                        view=view, 
                        ephemeral=True
                    )
                else:
                    await modal_interaction.response.send_message("Invalid script number.", ephemeral=True)
            except ValueError:
                await modal_interaction.response.send_message("Please enter a valid number.", ephemeral=True)
                
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Toggle", style=discord.ButtonStyle.secondary)
    async def toggle_script(self, interaction: discord.Interaction, button):
        # Create a modal to select which script to toggle
        modal = discord.ui.Modal(title="Toggle RegEx Script")
        
        script_select = discord.ui.TextInput(
            label="Script Number to Toggle",
            placeholder="Enter the number from the list",
            required=True
        )
        modal.add_item(script_select)
        
        async def on_submit(modal_interaction):
            try:
                script_idx = int(script_select.value) - 1
                scripts = self.manager.scripts
                    
                if 0 <= script_idx < len(scripts):
                    script = scripts[script_idx]
                    script.disabled = not script.disabled
                    
                    # Save the changes
                    self.manager.save_scripts()
                    
                    status = "disabled" if script.disabled else "enabled"
                    
                    # Generate a new embed with updated data
                    embed = await self.generate_embed(interaction)
                    
                    # Send a new message with the updated information instead of trying to edit the original
                    await modal_interaction.response.send_message(
                        f"Script '{script.name}' is now {status}. Here's the updated list:",
                        embed=embed,
                        view=self,
                        ephemeral=True
                    )
                else:
                    await modal_interaction.response.send_message("Invalid script number.", ephemeral=True)
            except ValueError:
                await modal_interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            except Exception as e:
                await modal_interaction.response.send_message(f"Error toggling script: {e}", ephemeral=True)
                
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Import", style=discord.ButtonStyle.secondary)
    async def import_script(self, interaction: discord.Interaction, button):
        await interaction.response.send_message(
            "To import a RegEx script, upload the .json file with your next message.", 
            ephemeral=True
        )
        
        # Setup a wait_for to process the uploaded file
        def check(message):
            return (message.author == interaction.user and 
                    message.channel == interaction.channel and 
                    len(message.attachments) > 0)
                    
        try:
            message = await self.manager.bot.wait_for('message', check=check, timeout=60.0)
            
            # Process the attachment
            if message.attachments:
                attachment = message.attachments[0]
                
                # Check file type
                if not attachment.filename.endswith('.json'):
                    await interaction.followup.send("Please upload a .json file.", ephemeral=True)
                    return
                    
                # Read file content
                content = await attachment.read()
                script_data = json.loads(content)
                
                scripts_added = []
                if isinstance(script_data, dict):
                    # Single script
                    script = RegexScript.from_dict(script_data)
                    self.manager.add_script(script)
                    scripts_added.append(script.name)
                    await interaction.followup.send(f"Imported RegEx script: {script.name}", ephemeral=True)
                elif isinstance(script_data, list):
                    # Multiple scripts
                    count = 0
                    for item in script_data:
                        script = RegexScript.from_dict(item)
                        self.manager.add_script(script)
                        scripts_added.append(script.name)
                        count += 1
                    await interaction.followup.send(f"Imported {count} RegEx scripts", ephemeral=True)
                
                # Try to update the original message view safely
                try:
                    # Generate a new embed with updated data
                    embed = await self.generate_embed(interaction)
                    
                    # Create a followup message with the updated view instead of editing
                    await interaction.followup.send(
                        content=f"Successfully imported scripts: {', '.join(scripts_added)}",
                        embed=embed,
                        view=self,
                        ephemeral=True
                    )
                except discord.NotFound:
                    # If the original message can't be found, just send a new message
                    await interaction.followup.send(
                        f"Scripts imported successfully. Use the RegEx management panel to see them.",
                        ephemeral=True
                    )
                except Exception as e:
                    # Log but don't fail if we can't update the UI
                    logger.error(f"Error updating UI after import: {e}")
                
        except asyncio.TimeoutError:
            await interaction.followup.send("Import timed out. Please try again.", ephemeral=True)
        except json.JSONDecodeError:
            await interaction.followup.send("Invalid JSON file. Please check your file and try again.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error importing script: {str(e)}", ephemeral=True)
            
    @discord.ui.button(label="Export", style=discord.ButtonStyle.secondary)
    async def export_script(self, interaction: discord.Interaction, button):
        # Create a modal to select which script to export
        modal = discord.ui.Modal(title="Export RegEx Script")
        
        script_select = discord.ui.TextInput(
            label="Script Number to Export",
            placeholder="Enter the number from the list (0 for all)",
            required=True
        )
        modal.add_item(script_select)
        
        async def on_submit(modal_interaction):
            try:
                script_idx = int(script_select.value)
                scripts = self.manager.scripts
                        
                if script_idx == 0:
                    # Export all scripts
                    script_data = [script.to_dict() for script in scripts]
                    filename = "regex_scripts.json"
                    
                    await modal_interaction.response.send_message(
                        "Here are your exported scripts:",
                        file=discord.File(
                            io.StringIO(json.dumps(script_data, indent=2)),
                            filename=filename
                        ),
                        ephemeral=True
                    )
                elif 1 <= script_idx <= len(scripts):
                    # Export single script
                    script = scripts[script_idx - 1]
                    script_data = script.to_dict()
                    filename = f"regex_script_{script.name}.json"
                    
                    await modal_interaction.response.send_message(
                        f"Here is your exported script '{script.name}':",
                        file=discord.File(
                            io.StringIO(json.dumps(script_data, indent=2)),
                            filename=filename
                        ),
                        ephemeral=True
                    )
                else:
                    await modal_interaction.response.send_message("Invalid script number.", ephemeral=True)
            except ValueError:
                await modal_interaction.response.send_message("Please enter a valid number.", ephemeral=True)
                
                
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button):
        if self.page > 0:
            self.page -= 1
            
        embed = await self.generate_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)
        
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button):
        scripts = self.manager.scripts
        
        max_pages = max((len(scripts) + self.page_size - 1) // self.page_size, 1)
        
        if self.page < max_pages - 1:
            self.page += 1
            
        embed = await self.generate_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def interaction_check(self, interaction: discord.Interaction):
        # Only allow the bot owner to use these controls
        if interaction.user.id != self.manager.bot.owner_id:
            await interaction.response.send_message("Only the bot owner can manage RegEx scripts.", ephemeral=True)
            return False
        return True