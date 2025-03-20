#!/bin/bash
# Copy config files to the selfhost directory
cp -v /app/config/character_config.json /app/selfhost/
cp -v /app/config/config.json /app/selfhost/
if [ -f /app/config/brain.json ]; then
    cp -v /app/config/brain.json /app/selfhost/
fi

# Create character_data directory if it doesn't exist
mkdir -p /app/selfhost/character_data

# Copy character_data if it exists
if [ -d /app/config/character_data ]; then
    cp -rv /app/config/character_data/* /app/selfhost/character_data/
fi

# Start the bot
cd /app/selfhost
python bot.py
