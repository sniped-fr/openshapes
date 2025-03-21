# OpenShapes

## An Open-Source Alternative to AI Characters

Welcome to OpenShapes, a community-driven, open-source alternative to the proprietary AI character platform shapes.inc. OpenShapes empowers you with full control over your AI companions through self-hosting or our upcoming managed service.

## Why OpenShapes?

- **Full Ownership**: Your characters, your data—no reliance on third-party platforms.
- **Customization**: Tailor every detail of your AI character’s behavior and responses.
- **Privacy**: Host your AI companions on your own infrastructure.
- **Cost-Effective**: Choose any AI model provider, including budget-friendly options.
- **Future-Proof**: No risk of service shutdowns or unexpected changes.

## Getting Started

Explore two ways to use OpenShapes:

### Option 1: Self-Hosting (Available Now)

Run your AI characters on your own infrastructure for complete control and flexibility.  
[**Go to Self-Hosting Guide →**](#self-hosting-guide)

### Option 2: Managed Service (Coming Soon)

Create and manage AI characters via our user-friendly platform—no technical setup required.  
_Stay tuned for updates!_

---

## Self-Hosting Guide

This guide walks you through setting up a self-hosted OpenShapes instance, whether migrating from shapes.inc or starting fresh.

### Prerequisites

- Basic command-line skills
- A Discord account and server with admin privileges
- Python 3.7+ installed

### Recommended Hosting Providers

For self-hosting, we recommend these providers:

#### AWS EC2 (Free Tier Available)

- **Why**: Free tier includes a t2.micro instance (1 vCPU, 1 GB RAM) for 12 months.
- **Setup Guide**:
  1. Sign up at [aws.amazon.com](https://aws.amazon.com).
  2. Navigate to EC2 > "Launch Instance."
  3. Choose "Ubuntu Server 22.04 LTS" (free tier eligible).
  4. Select "t2.micro" instance type > Launch.
  5. Download the `.pem` key file and connect via SSH:
     ```bash
     ssh -i your-key.pem ubuntu@your-ec2-public-ip
     ```
  6. Install dependencies (Python, Git, etc.) after connecting.

#### DigitalOcean

- **Why**: Affordable droplets starting at $4/month, reliable performance.
- **Setup Guide**:
  1. Sign up at [digitalocean.com](https://www.digitalocean.com).
  2. Create a Droplet: Choose "Ubuntu 22.04" and the $4/month plan (512 MB RAM).
  3. Copy the Droplet’s IP address.
  4. Connect via SSH:
     ```bash
     ssh root@your-droplet-ip
     ```
  5. Set up your environment with Python and Git.

Both providers support the steps below—use their SSH instructions to access your server.

### Migration Steps

#### Step 1: Export Your Character Data

To migrate from shapes.inc:

1. **Get main character data (shapes.json)**:

   ```
   https://shapes.inc/api/shapes/username/(YOUR_SHAPE_NAME)
   ```

   Replace `(YOUR_SHAPE_NAME)` with your character’s name.

2. **Get knowledge data (brain.json)**:

   ```
   https://shapes.inc/api/shapes/(YOUR_SHAPE_UNIQUE_ID)/story
   ```

   Find the unique ID in:

   - The URL: `https://shapes.inc/YOUR_SHAPE_NAME/readme`
   - Or `shapes.json` under `free_will_v2_ff`.

3. **Save files**:
   - Right-click each URL > "Save as..." (or Ctrl+S).
   - Name them `shapes.json` and `brain.json`.
   - Ensure you’re logged into shapes.inc.

#### Step 2: Set Up Your Discord Bot

1. **Create a Discord application**:

   - Visit [Discord Developer Portal](https://discord.com/developers/applications).
   - Click "New Application" > Name it > "Bot" tab > "Add Bot."
   - Enable all "Privileged Gateway Intents."
   - Disable "Public Bot" for privacy.

2. **Get your bot token**:

   - In the "Bot" tab, click "Reset Token" > Copy it securely.

3. **Invite the bot**:
   - Go to "OAuth2" > "URL Generator."
   - Select "bot" scope and permissions:
     - Read Messages/View Channels
     - Send Messages
     - Manage Messages
     - Embed Links
     - Attach Files
     - Read Message History
     - Add Reactions
   - Open the generated URL > Authorize to your server.

#### Step 3: Run the Migration Parser

1. **Organize files**:

   - Place `shapes.json` and `brain.json` in `openshapes/bot`.

2. **Run the parser**:

   ```bash
   python3 parser.py
   ```

3. **Follow prompts**:

   - Enter file paths (or press Enter for defaults).
   - Choose an output directory (or use current).

4. **Verify output**:
   - `character_config.json`
   - `character_data` folder with `memory.json` and `lorebook.json`.

#### Step 4: Configure and Start Your Bot

1. **Edit `character_config.json`**:

   - Add your bot token to `"bot_token"`.
   - Adjust settings as desired.

2. **Install OpenShapes**:

   ```bash
   git clone https://github.com/zukijourney/openshapes.git
   cd openshapes/bot
   pip install -r requirements.txt
   ```

3. **Copy files**:

   - Move `character_config.json` and `character_data` to the main directory.

4. **Launch the bot**:
   ```bash
   python3 bot.py
   ```

#### Step 5: Configure AI API Settings

1. **Set up your AI provider**:

   - In Discord, use `/api_settings` to select a provider (e.g., OpenAI, Anthropic, Zukijourney).
   - Input your API key and preferred model.

2. **Test it**:
   - Run `/character_info` to confirm setup.
   - Chat by mentioning the bot or messaging in an active channel.

### Troubleshooting

- **Bot offline?** Verify token and intents.
- **API issues?** Check key validity and credits.
- **Commands fail?** Confirm prefix (default: `/`).

### Advanced Configuration

- Tweak `character_config.json` for behavior.
- Use `/edit_personality_traits`, `/edit_backstory`, or `/regex` for customization.

## Default API Settings

OpenShapes defaults to Zukijourney’s API:

```json
"api_settings": {
  "base_url": "https://api.zukijourney.com/v1",
  "api_key": "zu-your-key-here",
  "chat_model": "llama-3.1-8b-instruct",
  "tts_model": "speechify",
  "tts_voice": "mrbeast"
}
```

Originating from this organization, ([zukijourney.com](https://zukijourney.com)), this is the default, but you can:

- Switch to any AI API provider.
- Explore free/affordable options at [CAS by Zukijourney](https://cas.zukijourney.com).

## Community and Support

- Discord: [https://discord.gg/8QSYftf48j](https://discord.gg/8QSYftf48j)
- GitHub: [https://github.com/zukijourney/openshapes](https://github.com/zukijourney/openshapes)

## Contributing

We welcome contributions! See our guidelines on GitHub.

## License

Licensed under AGPLv3—see the LICENSE file.

## Acknowledgments

- Gratitude to the ElectronHub and Zukijourney communities.
- Thanks to the AI character community and all contributors.

---

_OpenShapes is not affiliated with shapes.inc or any proprietary AI platform. This is a purely fan-made repository_
