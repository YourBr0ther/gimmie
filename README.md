# Gimmie - Track Your Wants & Needs

A family-focused PWA (Progressive Web App) for tracking wanted and needed items to prevent forgetting purchases between paydays.

## Features

- **Item Management**: Add, edit, delete, and reorder items in a single numbered list
- **Categories**: Mark items as "wants" or "needs"
- **Cost Tracking**: Track prices for budget planning
- **Purchase Links**: Save direct links to products
- **Import/Export**: Backup and restore your lists (JSON format)
- **Daily Backups**: Automatic daily backups at 2 AM
- **Mobile-First**: Optimized for mobile devices with PWA support
- **Offline Support**: Works offline once installed as a PWA

## Quick Start

### Local Development

1. Clone the repository
2. Copy `.env.example` to `.env` and set your password:
   ```bash
   cp .env.example .env
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the app:
   ```bash
   python app.py
   ```

5. Visit http://localhost:5010

### Docker Deployment

#### Option 1: Use Pre-built Image from Docker Hub
```bash
# Create .env file
cp .env.example .env

# Pull and run the latest image
docker run -d \
  --name gimmie \
  -p 5010:5010 \
  -v ./data:/app/data \
  --env-file .env \
  --restart unless-stopped \
  yourbr0ther/gimmie:latest
```

#### Option 2: Build from Source
1. Copy `.env.example` to `.env` and configure
2. Build and run:
   ```bash
   docker compose up -d
   ```

#### Docker Hub
The official image is available at: **[yourbr0ther/gimmie](https://hub.docker.com/r/yourbr0ther/gimmie)**

Available tags:
- `latest` - Latest stable version
- `v1.0` - Version 1.0 release

### Docker Swarm Deployment

For production environments with high availability:

#### Basic Swarm Deployment
```bash
# Initialize swarm (if not already done)
docker swarm init

# Deploy using the automated script
./deploy-swarm.sh
```

#### Production Swarm with Secrets
```bash
# Setup secrets first
./setup-swarm-secrets.sh

# Deploy production stack
docker stack deploy -c docker-compose.swarm.prod.yml gimmie
```

#### Swarm Management Commands
```bash
# View stack status
docker stack ps gimmie

# View services
docker stack services gimmie

# View logs
docker service logs gimmie_gimmie

# Scale the service
docker service scale gimmie_gimmie=3

# Remove the stack
docker stack rm gimmie
```

## PWA Installation

On mobile devices:
- iOS: Open in Safari, tap Share, then "Add to Home Screen"
- Android: Chrome will prompt to install, or use menu > "Add to Home Screen"

## Security

- Set a strong `LOGIN_PASSWORD` in your `.env` file
- Use HTTPS in production (configure reverse proxy)
- Change the `SECRET_KEY` for session encryption

## API Endpoints

- `POST /login` - Login with password
- `GET /api/items` - Get all items
- `POST /api/items` - Create new item
- `PUT /api/items/{id}` - Update item
- `DELETE /api/items/{id}` - Delete item
- `POST /api/items/{id}/complete` - Mark as completed
- `POST /api/items/{id}/move` - Move item up/down
- `GET /api/export` - Export data as JSON
- `POST /api/import` - Import data
- `GET /api/archive` - View archived items

## Technologies

- Backend: Python Flask
- Database: SQLite (upgradeable to PostgreSQL)
- Frontend: Vanilla JavaScript, CSS
- PWA: Service Worker, Web App Manifest
- Deployment: Docker