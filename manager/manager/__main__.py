import sys
import os
import dotenv
from .bot import OpenShapesManager

if __name__ == "__main__":
    dotenv.load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")))

    bot = OpenShapesManager()
    token = os.environ.get("DISCORD_BOT_TOKEN")

    if token == "YOUR_DISCORD_BOT_TOKEN":
        print("Please set your bot token in config/manager_config.json")
        sys.exit(1)

    bot.run(token)