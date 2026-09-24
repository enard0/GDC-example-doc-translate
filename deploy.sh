#!/bin/bash

if [ ! -f "images.tar" ]; then
    echo "Error: images.tar not found in the current directory."
    exit 1
fi

echo "Loading Docker images into the local registry..."
docker load -i images.tar

echo "Starting architecture..."
docker compose up -d

echo "Deployment complete. Use 'docker compose ps' to check status."