#!/bin/bash

TARGET_DIR=$1

if [ -z "$TARGET_DIR" ]; then
    echo "Usage: ./gather.sh /path/to/target_folder"
    exit 1
fi

if [ ! -d "models" ]; then
    echo "Error: Required directory 'models' does not exist."
    echo "please run build.sh"
    exit 1
fi

mkdir -p "$TARGET_DIR"

IMAGES=$(docker compose config | grep 'image:' | awk '{print $2}')

for IMAGE in $IMAGES; do
    if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
        echo "Error: Image '$IMAGE' not found locally."
        echo "please run build.sh"
        exit 1
    fi
done

echo "Exporting images to $TARGET_DIR/images.tar (This may take several minutes)..."
docker save -o "$TARGET_DIR/images.tar" $IMAGES

echo "Copying runtime configuration and files..."
cp docker-compose.yml "$TARGET_DIR/"
cp deploy.sh "$TARGET_DIR/"

if [ -f ".env" ]; then
    cp .env "$TARGET_DIR/"
fi

if [ -d "frontend" ]; then
    cp -r frontend "$TARGET_DIR/"
fi

cp -r models "$TARGET_DIR/"

echo "Gather complete. You can now transfer the '$TARGET_DIR'."