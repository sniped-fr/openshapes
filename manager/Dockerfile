FROM python:3.10-slim

COPY . /app

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    bash \
    && rm -rf /var/lib/apt/lists/

RUN pip install --no-cache-dir -r /app/bot/requirements.txt

RUN chmod +x /app/bot/run.sh

WORKDIR /app/bot

CMD ["bash"]