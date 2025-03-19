# OpenShapes

## An Open-Source Alternative to AI Characters

Welcome to OpenShapes, a community-driven, open-source alternative to the proprietary AI character platform shapes.inc. OpenShapes gives you full control over your AI companions by allowing you to self-host them or use our managed service (coming soon).

## Why OpenShapes?

- **Full Ownership**: Your characters, your data - no dependency on third-party platforms
- **Customization**: Modify every aspect of your AI character's behavior and responses
- **Privacy**: Host your AI companions on your own infrastructure
- **Cost-Effective**: Use any AI model provider of your choice, including more affordable options
- **Future-Proof**: No risk of service shutdowns or unwanted changes to your characters

## Getting Started

You have two main ways to use OpenShapes:

### Option 1: Self-Hosting (Available Now)

Self-host your AI characters on your own infrastructure. Complete control, maximum flexibility.
[**Go to Self-Hosting Guide →**](#self-hosting-guide)

### Option 2: Managed Service (Coming Soon)

Use our UI-based platform to create and manage your AI characters without technical setup.
_Stay tuned for updates!_

---

## Self-Hosting Guide

This guide will walk you through setting up your own self-hosted OpenShape from an existing shapes.inc character or creating a new one from scratch.

### Prerequisites

- Basic command line knowledge
- A Discord account and server where you have admin permissions
- Python 3.7 or higher installed

### Migration Steps

#### Step 1: Get Your Character Data

First, you need to export your character data from shapes.inc:

1. **Get your main character data (shapes.json)**:

   ```
   https://shapes.inc/api/shapes/username/(YOUR_SHAPE_NAME)
   ```

   Replace `(YOUR_SHAPE_NAME)` with your character's name from the config command.

2. **Get your character's knowledge data (brain.json)**:

   ```
   https://shapes.inc/api/shapes/(YOUR_SHAPE_UNIQUE_ID)/story
   ```

   To find your shape's unique ID, either:

   - Look at your character's URL on shapes.inc: `https://shapes.inc/YOUR_SHAPE_NAME/readme`
   - Or check inside your shapes.json file for the ID under `free_will_v2_ff` (use Ctrl+F to find it)

3. **Save both files**:
   - Right-click each page and select "Save as..." or press Ctrl+S
   - Save them as `shapes.json` and `brain.json` respectively
   - Make sure you're logged into shapes.inc when accessing these URLs

#### Step 2: Set Up Your Discord Bot

1. **Create a new Discord application**:

   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and give it a name
   - Go to the "Bot" tab and click "Add Bot"
   - Under "Privileged Gateway Intents", enable all intents
   - Scroll down and disable "Public Bot" if you want to keep it private

2. **Get your bot token**:

   - Click "Reset Token" and copy the new token
   - Keep this token secure - it gives full access to your bot!

3. **Invite the bot to your server**:
   - Go to the "OAuth2" tab, then "URL Generator"
   - Select "bot" under scopes
   - Select the following permissions:
     - Read Messages/View Channels
     - Send Messages
     - Manage Messages
     - Embed Links
     - Attach Files
     - Read Message History
     - Add Reactions
   - Copy the generated URL and open it in your browser
   - Select your server and authorize the bot

#### Step 3: Run the Migration Parser

1. **Place your files in the correct directory**:

   - Put your `shapes.json` and `brain.json` files in the `openshapes/selfhost` directory
   - The parser.py is already included in this directory

2. **Run the parser**:

   ```bash
   python3 parser.py
   ```

3. **Follow the prompts**:

   - Enter the path to your `shapes.json` file (or press Enter to use the one in the current directory)
   - Enter the path to your `brain.json` file (or press Enter to use the one in the current directory)
   - Choose an output directory (or press Enter for current directory)

4. **Check the output**:
   The script will create:
   - `character_config.json` in your output directory
   - A `character_data` folder containing `memory.json` and `lorebook.json`

#### Step 4: Configure and Start Your Bot

1. **Edit character_config.json**:

   - Add your Discord bot token to the `"bot_token"` field
   - Customize any other settings as needed

2. **Install the OpenShapes bot**:

   ```bash
   git clone https://github.com/zukijourney/openshapes.git
   cd openshapes/selfhost
   pip install -r requirements.txt
   ```

3. **Copy your configuration files**:

   - Copy the generated `character_config.json` to the main directory
   - Copy the `character_data` folder to the main directory

4. **Start the bot**:
   ```bash
   python3 bot.py
   ```

#### Step 5: Configure AI API Settings

1. **Set up your AI provider**:
   Use the `/api_settings` command in your Discord server to configure which AI provider to use:

   - Choose from supported providers like OpenAI, Anthropic, ZukiAI, etc.
   - Enter your API key
   - Select the model you want to use

2. **Test your character**:
   - Use `/character_info` to verify your character is set up correctly
   - Send a message in an activated channel or mention your bot to start chatting!

### Troubleshooting

- **Bot not responding?** Check that your bot token is correct and all intents are enabled
- **API errors?** Verify your API key is valid and has sufficient credits
- **Command not found?** Ensure you're using the correct command prefix (default is `/`)

### Advanced Configuration

- Edit the `character_config.json` file to customize behavior settings
- Use the `/edit_personality_traits` command to modify your character's traits
- Use the `/edit_backstory` command to change your character's history
- Use the `/regex` command to manage text pattern matching

## Default API Settings

By default, the configuration uses ZukiJourney's API:

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

## Community and Support

- Join our Discord community: [https://discord.gg/8QSYftf48j](https://discord.gg/8QSYftf48j)
- GitHub repository: [https://github.com/zukijourney/openshapes](https://github.com/zukijourney/openshapes)

## Contributing

OpenShapes is a community project, and we welcome contributions! Whether you're fixing bugs, adding features, or improving documentation, please check out our contribution guidelines.

## License

This project is licensed under the AGPLv3 License - see the LICENSE file for details.

## Acknowledgments

- Thanks to the ZukiJourney community for the inspiration and support
- Thanks to the AI character community for feedback
- Special thanks to all contributors who make this project possible

---

_OpenShapes is not affiliated with shapes.inc or any other proprietary AI character platform._
