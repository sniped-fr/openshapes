FROM python:3.10-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    bash \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/zukijourney/openshapes.git .

# Install required dependencies
RUN pip install --no-cache-dir \
    discord.py>=2.5.2 \
    openai>=1.66.5 \
    chromadb>=0.4.22 \
    aiohttp>=3.11.11

# Make sure run.sh is executable
RUN chmod +x /app/bot/run.sh

# Set the working directory to the bot folder
WORKDIR /app/bot

# Use bash to run the container
CMD ["bash"]