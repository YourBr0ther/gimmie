#!/bin/bash
# Script to rebuild and restart the Docker containers

# Stop existing containers
docker compose down

# Remove any existing volumes
docker volume prune -f

# Rebuild the image
docker compose build --no-cache

# Start the containers
docker compose up -d

echo "Gimmie app has been rebuilt and is now running on port 5010"
echo "Visit http://localhost:5010"
echo ""
echo "To view logs: docker compose logs -f"