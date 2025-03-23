#!/bin/bash
echo "Building OpenShapes Docker image..."
docker build -t openshapes -f Dockerfile .. > /dev/null 2>&1
echo "Starting the OpenShapes manager bot..."
python3 -B -m manager