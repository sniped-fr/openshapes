#!/bin/bash
docker build -t openshapes -f Dockerfile ..
python3 -B -m manager