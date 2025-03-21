import discord

def setup_tutorial_commands(bot, tutorial_commands):
    @tutorial_commands.command(
        name="token",
        description="Learn how to get a Discord bot token and enable intents",
    )
    async def token_tutorial_command(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        embed = discord.Embed(
            title="How to Get a Discord Bot Token and Enable Intents",
            description="This guide will walk you through creating a Discord bot application and getting your bot token.",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Step 1: Create a Discord Application",
            value="1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)\n"
            "2. Click the 'New Application' button\n"
            "3. Enter a name for your application and click 'Create'",
            inline=False,
        )

        embed.add_field(
            name="Step 2: Create a Bot",
            value="1. In your application, go to the 'Bot' tab on the left sidebar\n"
            "2. Click 'Add Bot' and confirm by clicking 'Yes, do it!'",
            inline=False,
        )

        embed.add_field(
            name="Step 3: Enable Intents",
            value="In the Bot tab, scroll down to 'Privileged Gateway Intents' and enable:\n"
            "• Presence Intent\n"
            "• Server Members Intent\n"
            "• Message Content Intent\n\n"
            "These are required for OpenShapes bots to function properly.",
            inline=False,
        )

        embed.add_field(
            name="Step 4: Get Your Bot Token",
            value="1. In the Bot tab, click the 'Reset Token' button\n"
            "2. Confirm the action\n"
            "3. Copy your token (it will only be shown once!)\n\n"
            "⚠️ **IMPORTANT**: Keep your token secret! Anyone with your token can control your bot.",
            inline=False,
        )

        embed.add_field(
            name="Step 5: Invite Your Bot to Servers",
            value="1. Go to the 'OAuth2' tab on the left sidebar\n"
            "2. Select 'URL Generator'\n"
            "3. In 'Scopes', select 'bot' and 'applications.commands'\n"
            "4. In 'Bot Permissions', select the permissions your bot needs\n"
            "5. Copy and open the generated URL to invite the bot to a server",
            inline=False,
        )

        embed.add_field(
            name="Using Your Token with OpenShapes",
            value="Use the `/create bot` command and provide:\n"
            "• A name for your bot\n"
            "• Your bot token\n"
            "• Your config.json file\n"
            "• Optionally, a brain.json file\n\n"
            "The bot will be created with your token and started automatically.",
            inline=False,
        )

        await interaction.followup.send(embed=embed)