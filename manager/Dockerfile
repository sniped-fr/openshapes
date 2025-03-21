FROM python:3.10-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/zukijourney/openshapes.git .

# Hardcode the requirements instead of using a file
RUN pip install --no-cache-dir \
    discord.py>=2.5.2 \
    openai>=1.66.5 \
    chromadb>=0.4.22 \
    aiohttp>=3.11.11

WORKDIR /app/bot

CMD ["python3", "bot.py"]