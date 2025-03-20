FROM python:3.10-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone the OpenShapes repository
RUN git clone https://github.com/zukijourney/openshapes.git .

# Install Python dependencies from the selfhost directory
RUN pip install --no-cache-dir -r selfhost/requirements.txt

# Set up the selfhost directory
WORKDIR /app/selfhost

# Entry point will be set by the container command
CMD ["python3", "bot.py"]