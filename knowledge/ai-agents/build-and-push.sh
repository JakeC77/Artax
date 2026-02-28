#!/bin/bash
# Build and push Docker image to Azure Container Registry
#
# Usage:
#   ./build-and-push.sh <ACR_NAME> <IMAGE_NAME> [TAG]
#
# Example:
#   ./build-and-push.sh myregistry.azurecr.io geodesicworks-ai-app latest

set -e

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <ACR_NAME> <IMAGE_NAME> [TAG]"
    echo "Example: $0 myregistry.azurecr.io geodesicworks-ai-app latest"
    exit 1
fi

ACR_NAME=$1
IMAGE_NAME=$2
TAG=${3:-latest}

# Full image name
FULL_IMAGE_NAME="${ACR_NAME}/${IMAGE_NAME}:${TAG}"

echo "=========================================="
echo "Building Docker image for Azure Container App"
echo "=========================================="
echo "ACR: $ACR_NAME"
echo "Image: $IMAGE_NAME"
echo "Tag: $TAG"
echo "Full name: $FULL_IMAGE_NAME"
echo ""

# Navigate to the directory containing this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Build context: need to go up to project root to include geodesic package
# Build from app directory with context at project root
echo "Building Docker image..."
docker build \
    -f Dockerfile \
    -t "$FULL_IMAGE_NAME" \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    -t "${ACR_NAME}/${IMAGE_NAME}:latest" \
    ../

echo ""
echo "Build complete!"
echo ""

# Login to ACR (if not already logged in)
echo "Logging in to Azure Container Registry..."
az acr login --name geodesicworks

# Push image
echo ""
echo "Pushing image to ACR..."
docker push "$FULL_IMAGE_NAME"
docker push "${ACR_NAME}/${IMAGE_NAME}:latest"

echo ""
echo "=========================================="
echo "Successfully pushed to ACR!"
echo "Image: $FULL_IMAGE_NAME"
echo "=========================================="




