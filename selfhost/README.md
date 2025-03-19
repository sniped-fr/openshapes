# OpenShapes Self-Hosting Guide

This detailed guide will walk you through the process of self-hosting your own OpenShape, either by migrating from shapes.inc or creating a new character from scratch.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Migration from shapes.inc](#migration-from-shapesinc)
- [Setting Up Your Discord Bot](#setting-up-your-discord-bot)
- [Running the Migration Parser](#running-the-migration-parser)
- [Configuring and Starting the Bot](#configuring-and-starting-the-bot)
- [AI API Configuration](#ai-api-configuration)
- [Character Commands and Features](#character-commands-and-features)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, make sure you have:

- Python 3.7 or higher installed
- Basic knowledge of command-line operations
- A Discord account with a server where you have admin permissions
- (Optional) An account on shapes.inc if you're migrating an existing character

## Migration from shapes.inc

### Step 1: Export Your Character Data

To migrate your existing character from shapes.inc, you'll need to export two JSON files:

#### 1.1 Get your shapes.json file

This contains your character's personality, appearance, and system configuration:

1. Make sure you're logged into shapes.inc
2. Visit the URL below, replacing `(YOUR_SHAPE_NAME)` with your character's name:
   ```
   https://shapes.inc/api/shapes/username/(YOUR_SHAPE_NAME)
   ```
3. The browser will display a JSON file. Press `Ctrl+S` (or `Cmd+S` on Mac) to save it as `shapes.json`

#### 1.2 Get your brain.json file

This contains your character's knowledge base:

1. You'll need to find your character's unique ID, which is NOT the Discord bot ID
2. The unique ID can be found in one of two ways:

   - **Method 1**: Look in your `shapes.json` file for the ID under the `free_will_v2_ff` property (use Ctrl+F to find it)
   - **Method 2**: Your character's URL pattern contains the ID. If you visit:
     ```
     https://shapes.inc/YOUR_SHAPE_NAME/readme
     ```
     You can extract the ID from there

3. Once you have the unique ID, visit:
   ```
   https://shapes.inc/api/shapes/(YOUR_SHAPE_UNIQUE_ID)/story
   ```
4. Save this file as `brain.json` using `Ctrl+S` or `Cmd+S`

### Step 2: Keep These Files Safe

Store your `shapes.json` and `brain.json` files in a folder where you'll run the migration parser. These files contain all your character's data.

## Setting Up Your Discord Bot

### Step 1: Create a Discord Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click the "New Application" button in the top right
3. Give your application a name (this will be your bot's initial username)
4. Click "Create"

### Step 2: Set Up the Bot User

1. In the left sidebar, click on "Bot"
2. Click the "Add Bot" button and confirm by clicking "Yes, do it!"
3. Under the "Privileged Gateway Intents" section, enable ALL three toggles:
   - Presence Intent
   - Server Members Intent
   - Message Content Intent
4. Click on "Reset Token" and copy your bot token
   - ⚠️ **IMPORTANT**: Keep this token secure! Anyone with this token can control your bot
   - Consider saving it in a password manager or secure note
5. Disable "Public Bot" if you want to prevent others from inviting your bot to their servers

### Step 3: Invite Your Bot to Your Server

1. In the left sidebar, click on "OAuth2" and then "URL Generator"
2. Under "Scopes", check "bot"
3. Under "Bot Permissions", select the following:
   - Read Messages/View Channels
   - Send Messages
   - Manage Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Add Reactions
   - Use Slash Commands
4. Copy the generated URL at the bottom of the page
5. Paste the URL in a new browser tab
6. Select the server where you want to add the bot
7. Click "Authorize" and complete any verification steps

## Running the Migration Parser

### Step 1: Set Up the Parser

1. The migration parser script (`parser.py`) is already included in the `openshapes/selfhost` directory
2. Place your `shapes.json` and `brain.json` files in this same directory

### Step 2: Run the Parser

1. Open a command prompt or terminal in the folder containing your files
2. Run the parser with:
   ```bash
   python parser.py
   ```
3. When prompted, enter the paths to your files:
   - For `shapes.json`, either enter the full path or just press Enter if it's in the current directory
   - For `brain.json`, either enter the full path or just press Enter if it's in the current directory
   - For the output directory, either specify a path or press Enter to use the current directory

### Step 3: Check the Output

The parser will generate:

- `character_config.json` in your output directory
- A `character_data` folder containing:
  - `memory.json`
  - `lorebook.json`

These files contain all the information needed for your OpenShape.

## Configuring and Starting the Bot

### Step 1: Install the OpenShapes Bot

1. Clone the OpenShapes repository:

   ```bash
   git clone https://github.com/zukijourney/openshapes.git
   cd openshapes/selfhost
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Step 2: Configure Your Bot

1. Open the generated `character_config.json` file in a text editor
2. Add your Discord bot token to the `"bot_token"` field:
   ```json
   "bot_token": "YOUR_DISCORD_BOT_TOKEN_HERE",
   ```
3. Configure the `"owner_id"` field with your Discord user ID
4. Customize other settings as desired:
   - `"character_name"`: Your character's display name
   - `"command_prefix"`: The prefix for commands (default is `/`)
   - `"always_reply_mentions"`: Whether the bot responds to mentions
   - `"use_tts"`: Whether the bot uses text-to-speech for responses

### Step 3: Check Configuration Files

The parser generates the configuration files directly in the correct directory:

- `character_config.json` should be in the `openshapes/selfhost` directory
- `character_data` folder should be in the `openshapes/selfhost` directory

Ensure these files are in place before continuing.

### Step 4: Start the Bot

From the `openshapes/selfhost` directory, run:

```bash
python bot.py
```

Your OpenShape should now be online in your Discord server!

## AI API Configuration

### Step 1: Choose an AI Provider

OpenShapes supports multiple AI providers. Configure your preferred provider using the `/api_settings` command in Discord:

1. Type `/api_settings` in a Discord channel where your bot has access
2. The bot will guide you through setting up:
   - API provider (OpenAI, Anthropic, ZukiAI, etc.)
   - API key
   - Model selection
   - Optional: TTS voice configuration

### Step 2: Default API Settings

If you don't change the settings, the default configuration in your `character_config.json` is:

```json
"api_settings": {
    "base_url": "https://api.zukijourney.com/v1",
    "api_key": "zu-myballs",
    "chat_model": "llama-3.1-8b-instruct",
    "tts_model": "speechify",
    "tts_voice": "mrbeast"
}
```

Since the OpenShapes project originated from the ZukiJourney community (https://zukijourney.com), their API is set as the default, but you're encouraged to:

- Use any AI API provider of your choice
- Look for free or affordable options on [CAS ZukiJourney](https://cas.zukijourney.com)

You should definitely change these settings to use your own API keys.

## Character Commands and Features

Your OpenShape comes with several commands and features as shown in the help guide:

### Basic Interaction

- In activated channels: The bot responds to all messages automatically
- In other channels: Mention the bot (@BotName) or use its name in your message
- Use 🗑️ to delete bot messages, 🔄 to regenerate responses

### Character Commands

- `/character_info` - View description, traits, and backstory
- `/activate` - Make bot respond to all messages in the channel
- `/deactivate` - Bot only responds when mentioned or called by name

### Memory System

- The bot remembers important information from conversations
- `/memory` - View what the bot has remembered
- `/sleep` - Process recent conversations into long-term memories

### Lorebook

- Custom knowledge base that influences the bot's understanding
- `/lorebook` - View entries in the lorebook
- Perfect for worldbuilding and custom knowledge

### Owner Controls

- `/settings` - Manage bot behavior settings
- `/api_settings` - Configure AI API settings
- `/edit_personality_traits` - Customize character traits
- `/edit_backstory` - Change character history
- `/edit_likes_dislikes` - Set likes and dislikes
- `/edit_prompt` - Change system prompt
- `/edit_description` - Modify character description
- `/edit_scenario` - Set interaction scenario
- `/regex` - Manage text pattern manipulation
- `/blacklist` - Manage user access
- `/save` - Save all current data

## Advanced Configuration

### Customizing Your Character's Behavior

The `character_config.json` file contains several parameters you can modify:

- **Personality Settings**: Edit traits, history, likes/dislikes
- **Conversation Settings**: Adjust how the bot responds in conversations
- **API Settings**: Change AI model, parameters, and other settings
- **Access Control**: Manage which users and channels the bot interacts with

### Character Development

- Use the memory system to build your character's knowledge over time
- Add entries to the lorebook for specific knowledge or context
- Adjust response patterns using regex for consistent character behavior

## Troubleshooting

### Common Issues and Solutions

- **Bot Not Responding**:

  - Check that your bot token is correct
  - Verify all privileged intents are enabled in the Discord Developer Portal
  - Ensure the bot has proper permissions in the Discord server

- **API Connection Issues**:

  - Verify your API key is valid and has sufficient credits
  - Check your internet connection
  - Make sure the API endpoint is correct

- **Bot Crashing**:

  - Check console for error messages
  - Verify your character configuration files are valid JSON
  - Ensure all dependencies are installed

- **Response Quality Issues**:
  - Try a different AI model
  - Adjust the system prompt for better character guidance
  - Add more detailed information to the character's memory and lorebook

---

## Support and Community

If you encounter issues or have questions, join our community:

- Discord: [Join OpenShapes Community](https://discord.gg/8QSYftf48j)
- GitHub: [Report Issues](https://github.com/zukijourney/openshapes/issues)
- ZukiJourney Community: [discord.gg/zukijourney](https://discord.gg/zukijourney)

---

_OpenShapes is a community-driven project not affiliated with shapes.inc or any other proprietary AI character platform._
