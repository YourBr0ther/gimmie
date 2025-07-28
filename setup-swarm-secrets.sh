#!/bin/bash

# Gimmie Docker Swarm Secrets Setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔐 Gimmie Docker Swarm Secrets Setup${NC}"
echo "========================================"

# Check if Docker Swarm is active
if ! docker info | grep -q "Swarm: active"; then
    echo -e "${RED}❌ Docker Swarm is not active${NC}"
    echo "Please run 'docker swarm init' first"
    exit 1
fi

# Generate or prompt for secret key
if [ -z "$SECRET_KEY" ]; then
    echo -e "${YELLOW}🔑 Generating SECRET_KEY...${NC}"
    SECRET_KEY=$(openssl rand -hex 32)
    echo -e "${GREEN}✅ Generated SECRET_KEY${NC}"
else
    echo -e "${GREEN}✅ Using provided SECRET_KEY${NC}"
fi

# Prompt for login password
if [ -z "$LOGIN_PASSWORD" ]; then
    echo -e "${YELLOW}🔒 Enter LOGIN_PASSWORD:${NC}"
    read -s LOGIN_PASSWORD
    echo ""
fi

# Create secrets
echo -e "${BLUE}📝 Creating Docker secrets...${NC}"

# Remove existing secrets if they exist
docker secret rm gimmie_secret_key 2>/dev/null || true
docker secret rm gimmie_login_password 2>/dev/null || true

# Create new secrets
echo "$SECRET_KEY" | docker secret create gimmie_secret_key -
echo "$LOGIN_PASSWORD" | docker secret create gimmie_login_password -

echo -e "${GREEN}✅ Secrets created successfully!${NC}"

# List secrets
echo -e "${BLUE}📋 Created secrets:${NC}"
docker secret ls | grep gimmie

echo ""
echo -e "${GREEN}🎉 Setup complete!${NC}"
echo "You can now deploy with: docker stack deploy -c docker-compose.swarm.prod.yml gimmie"