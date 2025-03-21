#!/bin/bash

CONFIG="character_config.json"
DEBUG=false

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [ "$DEBUG" = true ]; then
    LOG_LEVEL="DEBUG"
else
    LOG_LEVEL="INFO"
fi

echo "Starting OpenShape bot with config: $CONFIG"

if [ ! -f "$CONFIG" ]; then
    echo "Error: Configuration file not found: $CONFIG" >&2
    exit 1
fi

python3 - <<EOF
import sys
import logging
from openshapes import OpenShape

logging.basicConfig(level=logging.$LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("openshape")

try:
    bot = OpenShape("$CONFIG")
    bot.run(bot.character_config.get("bot_token", ""))
except Exception as e:
    logger.error(f"Error running bot: {e}", exc_info=True)
    sys.exit(1)
EOF
