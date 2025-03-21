import discord
from discord import app_commands
from typing import Any, Dict, List


class TutorialEmbed:
    def __init__(self, title: str, description: str, color: discord.Color = discord.Color.blue()):
        self.title = title
        self.description = description
        self.color = color
        self.fields: List[Dict[str, Any]] = []
    
    def add_field(self, name: str, value: str, inline: bool = False) -> None:
        self.fields.append({
            "name": name,
            "value": value,
            "inline": inline
        })
    
    def build(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            color=self.color
        )
        
        for field in self.fields:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field["inline"]
            )
            
        return embed


class BotTokenTutorial:
    def __init__(self):
        self.title = "How to Get a Discord Bot Token and Enable Intents"
        self.description = "This guide will walk you through creating a Discord bot application and getting your bot token."
    
    def create_embed(self) -> discord.Embed:
        tutorial_embed = TutorialEmbed(self.title, self.description)
        
        tutorial_embed.add_field(
            name="Step 1: Create a Discord Application",
            value="1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)\n"
                  "2. Click the 'New Application' button\n"
                  "3. Enter a name for your application and click 'Create'",
            inline=False
        )
        
        tutorial_embed.add_field(
            name="Step 2: Create a Bot",
            value="1. In your application, go to the 'Bot' tab on the left sidebar\n"
                  "2. Click 'Add Bot' and confirm by clicking 'Yes, do it!'",
            inline=False
        )
        
        tutorial_embed.add_field(
            name="Step 3: Enable Intents",
            value="In the Bot tab, scroll down to 'Privileged Gateway Intents' and enable:\n"
                  "• Presence Intent\n"
                  "• Server Members Intent\n"
                  "• Message Content Intent\n\n"
                  "These are required for OpenShapes bots to function properly.",
            inline=False
        )
        
        tutorial_embed.add_field(
            name="Step 4: Get Your Bot Token",
            value="1. In the Bot tab, click the 'Reset Token' button\n"
                  "2. Confirm the action\n"
                  "3. Copy your token (it will only be shown once!)\n\n"
                  "⚠️ **IMPORTANT**: Keep your token secret! Anyone with your token can control your bot.",
            inline=False
        )
        
        tutorial_embed.add_field(
            name="Step 5: Invite Your Bot to Servers",
            value="1. Go to the 'OAuth2' tab on the left sidebar\n"
                  "2. Select 'URL Generator'\n"
                  "3. In 'Scopes', select 'bot' and 'applications.commands'\n"
                  "4. In 'Bot Permissions', select the permissions your bot needs\n"
                  "5. Copy and open the generated URL to invite the bot to a server",
            inline=False
        )
        
        tutorial_embed.add_field(
            name="Using Your Token with OpenShapes",
            value="Use the `/create bot` command and provide:\n"
                  "• A name for your bot\n"
                  "• Your bot token\n"
                  "• Your config.json file\n"
                  "• Optionally, a brain.json file\n\n"
                  "The bot will be created with your token and started automatically.",
            inline=False
        )
        
        return tutorial_embed.build()


class TutorialCommandsManager:
    def __init__(self, bot):
        self.bot = bot
        self.tutorials = {
            "token": BotTokenTutorial()
        }
    
    def register_commands(self, command_group: app_commands.Group) -> None:
        @command_group.command(
            name="token",
            description="Learn how to get a Discord bot token and enable intents"
        )
        async def token_tutorial_command(interaction: discord.Interaction) -> None:
            await interaction.response.defer(thinking=True)
            
            bot_token_tutorial = self.tutorials["token"]
            embed = bot_token_tutorial.create_embed()
            
            await interaction.followup.send(embed=embed)


def setup_tutorial_commands(bot, tutorial_commands):
    tutorial_manager = TutorialCommandsManager(bot)
    tutorial_manager.register_commands(tutorial_commands)
