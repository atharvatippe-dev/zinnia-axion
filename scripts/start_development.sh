#!/bin/bash
set -e

echo "Starting Zinnia Axion Backend (Development Mode)"
source .venv/bin/activate
python3 -m flask run --host=0.0.0.0 --port=5000 --debug
