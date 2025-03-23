import sys
import os
import dotenv
from manager.bot import OpenShapesManager

dotenv.load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")))

bot = OpenShapesManager()
token = os.environ.get("DISCORD_BOT_TOKEN")

if not token:
    print("Please set your bot token in .env")
    sys.exit(1)

bot.run(token)