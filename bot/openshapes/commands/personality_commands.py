import discord
from openshapes.utils.views import TextEditModal
import logging

logger = logging.getLogger("openshape")

async def edit_personality_traits_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can use this command", ephemeral=True
        )
        return

    options = [
        discord.SelectOption(label="Catchphrases", value="catchphrases"),
        discord.SelectOption(label="Age", value="age"),
        discord.SelectOption(label="Traits", value="traits"),
        discord.SelectOption(label="Physical Traits", value="physical"),
        discord.SelectOption(label="Tone", value="tone"),
        discord.SelectOption(label="Conversational Style", value="style"),
    ]

    select = discord.ui.Select(placeholder="Select trait to edit", options=options)

    async def select_callback(select_interaction):
        trait = select.values[0]
        
        current_values = {
            "catchphrases": self.personality_catchphrases,
            "age": self.personality_age,
            "traits": self.personality_traits,
            "physical": self.personality_physical_traits,
            "tone": self.personality_tone,
            "style": self.personality_conversational_examples
        }
        
        modal = TextEditModal(
            title=f"Edit {trait.title()}", 
            current_text=current_values[trait] or ""
        )

        async def on_submit(modal_interaction):
            if trait == "catchphrases":
                self.personality_catchphrases = modal.text_input.value
            elif trait == "age":
                self.personality_age = modal.text_input.value
            elif trait == "traits":
                self.personality_traits = modal.text_input.value
            elif trait == "physical":
                self.personality_physical_traits = modal.text_input.value
            elif trait == "tone":
                self.personality_tone = modal.text_input.value
            elif trait == "style":
                self.personality_conversational_examples = modal.text_input.value
                
            self.config_manager.save_config()
            await modal_interaction.response.send_message(
                f"Character {trait} updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await select_interaction.response.send_modal(modal)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)

    await interaction.response.send_message(
        "Select a personality trait to edit:", view=view, ephemeral=True
    )

async def edit_backstory_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can use this command", ephemeral=True
        )
        return

    modal = TextEditModal(
        title="Edit Character History", 
        current_text=self.personality_history or ""
    )

    async def on_submit(modal_interaction):
        self.personality_history = modal.text_input.value
        self.config_manager.save_config()
        await modal_interaction.response.send_message(
            "Character history updated!", ephemeral=True
        )

    modal.on_submit = on_submit
    await interaction.response.send_modal(modal)

async def edit_preferences_command(self, interaction: discord.Interaction):
    if interaction.user.id != self.owner_id:
        await interaction.response.send_message(
            "Only the bot owner can use this command", ephemeral=True
        )
        return

    options = [
        discord.SelectOption(label="Likes", value="likes"),
        discord.SelectOption(label="Dislikes", value="dislikes"),
        discord.SelectOption(label="Goals", value="goals"),
    ]

    select = discord.ui.Select(placeholder="Select preference to edit", options=options)

    async def select_callback(select_interaction):
        pref = select.values[0]
        
        current_values = {
            "likes": self.personality_likes,
            "dislikes": self.personality_dislikes,
            "goals": self.personality_goals
        }
        
        modal = TextEditModal(
            title=f"Edit {pref.title()}", 
            current_text=current_values[pref] or ""
        )

        async def on_submit(modal_interaction):
            if pref == "likes":
                self.personality_likes = modal.text_input.value
            elif pref == "dislikes":
                self.personality_dislikes = modal.text_input.value
            elif pref == "goals":
                self.personality_goals = modal.text_input.value
                
            self.config_manager.save_config()
            await modal_interaction.response.send_message(
                f"Character {pref} updated!", ephemeral=True
            )

        modal.on_submit = on_submit
        await select_interaction.response.send_modal(modal)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)

    await interaction.response.send_message(
        "Select preferences to edit:", view=view, ephemeral=True
    )
