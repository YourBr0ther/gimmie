#!/bin/bash

# Gimmie Multi-Architecture Docker Build & Push

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DOCKER_REPO="yourbr0ther/gimmie"
VERSION=${1:-"latest"}

echo -e "${YELLOW}🏗️  Multi-Architecture Docker Build${NC}"
echo "========================================="

# Check if logged into Docker Hub
if ! cat ~/.docker/config.json 2>/dev/null | grep -q "index.docker.io"; then
    echo -e "${RED}❌ Not logged into Docker Hub${NC}"
    echo "Please run: docker login"
    exit 1
fi

# Create and use buildx builder
echo -e "${YELLOW}🔧 Setting up multi-arch builder...${NC}"
docker buildx create --name multiarch-builder --use 2>/dev/null || docker buildx use multiarch-builder

# Enable experimental features
export DOCKER_CLI_EXPERIMENTAL=enabled

# Build and push multi-architecture image
echo -e "${YELLOW}🚀 Building for multiple architectures...${NC}"
docker buildx build \
    --platform linux/amd64,linux/arm64,linux/arm/v7 \
    --tag ${DOCKER_REPO}:${VERSION} \
    --tag ${DOCKER_REPO}:latest \
    --push \
    .

echo -e "${GREEN}✅ Multi-arch build completed!${NC}"
echo ""
echo "🎉 Image available for:"
echo "   • linux/amd64 (Intel/AMD)"
echo "   • linux/arm64 (ARM 64-bit)"
echo "   • linux/arm/v7 (ARM 32-bit)"
echo ""
echo "📋 To use:"
echo "   docker pull ${DOCKER_REPO}:${VERSION}"