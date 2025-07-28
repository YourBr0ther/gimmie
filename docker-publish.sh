#!/bin/bash

# Gimmie Docker Hub Publishing Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🐳 Gimmie Docker Hub Publishing Script${NC}"
echo "============================================"

# Check if logged into Docker Hub
if ! docker info | grep -q "Username:"; then
    echo -e "${RED}❌ Not logged into Docker Hub${NC}"
    echo "Please run: docker login"
    exit 1
fi

# Get version from user input or use default
VERSION=${1:-"latest"}
DOCKER_REPO="yourbrother/gimmie"

echo -e "${YELLOW}📦 Building image: ${DOCKER_REPO}:${VERSION}${NC}"

# Build the image
docker build -t ${DOCKER_REPO}:${VERSION} -t ${DOCKER_REPO}:latest .

echo -e "${GREEN}✅ Build completed successfully${NC}"

echo -e "${YELLOW}🚀 Pushing to Docker Hub...${NC}"

# Push both tags
docker push ${DOCKER_REPO}:${VERSION}
if [ "$VERSION" != "latest" ]; then
    docker push ${DOCKER_REPO}:latest
fi

echo -e "${GREEN}✅ Successfully pushed to Docker Hub!${NC}"
echo ""
echo "🎉 Your image is now available at:"
echo "   https://hub.docker.com/r/${DOCKER_REPO}"
echo ""
echo "📋 To use the image:"
echo "   docker pull ${DOCKER_REPO}:${VERSION}"
echo "   docker run -d -p 5010:5010 -v ./data:/app/data ${DOCKER_REPO}:${VERSION}"