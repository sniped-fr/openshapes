FROM python:3.10-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/zukijourney/openshapes.git .

RUN pip install --no-cache-dir -r bot/requirements.txt

WORKDIR /app/bot

CMD ["python3", "bot.py"]