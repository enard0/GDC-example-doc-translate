#!/bin/bash
set -e

# Configuration
MODELS_DIR="./models"
LLM_DIR="./Hy-MT2-7B"

echo "Initializing build process..."

# 1. Create necessary directories
mkdir -p "$MODELS_DIR"
mkdir -p "$LLM_DIR"

# 2. Build Docker Images FIRST
echo "Building Docker images..."
docker compose build

# 3. Download Translation Model via temporary Python container
echo "Fetching Translation Model (Hy-MT2-7B)..."
if [ ! -f "$LLM_DIR/config.json" ]; then
    # Użycie oficjalnego, lekkiego obrazu pythona z zainstalowanym huggingface_hub
    docker run --rm -v "$(pwd)/$LLM_DIR:/app/model" python:3.10-slim bash -c "
        pip install huggingface_hub && \
        hf download tencent/Hy-MT2-7B --local-dir /app/model
    "
else
    echo "Translation model files already exist. Skipping download."
fi

# 4. Download Paddle models using the built OCR container
echo "Fetching Paddle models..."

# Uruchomienie skryptu z zamontowanym wolumenem lokalnym ./models do /models
docker compose run --rm \
    -v "$(pwd)/models:/root/.paddlex/official_models" \
    -v "$(pwd)/init_paddle.py:/app/init_paddle.py" \
    ocr \
    python3 /app/init_paddle.py

# 5. Clean up environment and free resources
echo "Shutting down temporary containers and freeing resources..."
docker compose down --remove-orphans

# 6. Deploy Containers
echo "Deploying services..."
docker compose up -d

echo "Deployment complete. Services are running in the background."