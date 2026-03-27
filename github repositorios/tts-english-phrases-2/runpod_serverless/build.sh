#!/usr/bin/env bash
# Build and push the Kokoro TTS serverless image to Docker Hub.
#
# Usage:
#   DOCKER_USER=myusername bash build.sh
#   DOCKER_USER=myusername TAG=v1.1 bash build.sh
set -e

if [ -z "$DOCKER_USER" ]; then
  echo "Error: DOCKER_USER is not set."
  echo "Usage: DOCKER_USER=myusername bash build.sh"
  exit 1
fi

IMAGE_NAME="$DOCKER_USER/kokoro-tts"
TAG="${TAG:-latest}"
FULL_IMAGE="$IMAGE_NAME:$TAG"

echo "==> Building $FULL_IMAGE (linux/amd64) ..."
docker build --platform linux/amd64 -t "$FULL_IMAGE" .

echo "==> Pushing $FULL_IMAGE ..."
docker push "$FULL_IMAGE"

echo ""
echo "Done! Use this image in your RunPod Serverless endpoint:"
echo "  $FULL_IMAGE"
