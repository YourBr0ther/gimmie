#!/bin/bash

# Gimmie Docker Swarm Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

STACK_NAME="gimmie"
COMPOSE_FILE="docker-compose.swarm.yml"

echo -e "${BLUE}🐳 Gimmie Docker Swarm Deployment${NC}"
echo "======================================="

# Check if Docker Swarm is initialized
if ! docker info | grep -q "Swarm: active"; then
    echo -e "${YELLOW}⚠️  Docker Swarm not initialized${NC}"
    echo "Do you want to initialize Docker Swarm? (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo -e "${BLUE}🔧 Initializing Docker Swarm...${NC}"
        docker swarm init
        echo -e "${GREEN}✅ Docker Swarm initialized${NC}"
    else
        echo -e "${RED}❌ Docker Swarm required for deployment${NC}"
        exit 1
    fi
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env from template..."
    cp .env.example .env
    echo -e "${YELLOW}📝 Please edit .env file with your settings${NC}"
    echo "Press Enter when ready to continue..."
    read -r
fi

# Deploy the stack
echo -e "${BLUE}🚀 Deploying Gimmie stack...${NC}"
docker stack deploy -c $COMPOSE_FILE $STACK_NAME

echo -e "${GREEN}✅ Deployment completed!${NC}"
echo ""
echo "📊 Stack Status:"
docker stack ps $STACK_NAME

echo ""
echo "🔍 Available Commands:"
echo "  docker stack ps $STACK_NAME          # View service status"
echo "  docker stack services $STACK_NAME    # View services"
echo "  docker service logs ${STACK_NAME}_gimmie  # View logs"
echo "  docker stack rm $STACK_NAME          # Remove stack"
echo ""
echo "🌐 Access your app at: http://localhost:5010"