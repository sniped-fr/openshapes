FROM python:3.11-slim

COPY . /app

WORKDIR /app

RUN pip install --upgrade --no-cache-dir -r /app/bot/requirements.txt

RUN apt-get update && apt-get install -y dos2unix \
    && find /app -name "*.sh" -exec dos2unix {} \; \
    && chmod +x /app/bot/run.sh

WORKDIR /app/bot

CMD ["bash"]