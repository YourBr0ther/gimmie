# Gimmie App - Technical Specification

## Project Overview

**App Name**: Gimmie  
**Purpose**: A family-focused web application for tracking wanted and needed items to prevent forgetting purchases between paydays.  
**Technology Stack**: Python (Flask/FastAPI), Docker, SQLite/PostgreSQL, HTML/CSS/JavaScript  
**Deployment**: Self-hosted on personal server, accessible via web on mobile devices

## Core Features

### 1. Item Management
- Single numbered list displaying all items
- Each item contains:
  - Item name (text)
  - Cost (decimal number)
  - Purchase link (URL)
  - Type (Want or Need)
  - List position (auto-managed)
- Actions per item:
  - Move up (swap with item above)
  - Move down (swap with item below)
  - Delete (move to archive)
  - Complete (mark as purchased, move to archive)

### 2. User Interface
- Mobile-first responsive design
- Clean, simple interface optimized for touch
- Real-time list reordering
- Visual distinction between wants and needs

### 3. Authentication
- Simple login page
- Session-based authentication using tokens
- Long-lived sessions to minimize re-authentication
- Single shared family account (no multi-user complexity needed)

### 4. Data Management
- Import/Export functionality (CSV or JSON format)
- Automated daily backups
- Archive system for deleted/completed items
- Data persistence using SQLite (upgradeable to PostgreSQL)

## Technical Architecture

### Backend Structure
```
gimmie/
├── app.py                 # Main Flask/FastAPI application
├── models.py             # Database models
├── auth.py               # Authentication logic
├── backup.py             # Backup automation
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker compose setup
├── static/
│   ├── css/
│   │   └── style.css    # Mobile-first styles
│   └── js/
│       └── app.js       # Frontend JavaScript
├── templates/
│   ├── login.html       # Login page
│   ├── index.html       # Main list view
│   └── base.html        # Base template
├── data/
│   ├── gimmie.db        # SQLite database
│   └── backups/         # Daily backup storage
└── tests/
    └── test_app.py      # Basic tests
```

### Database Schema

```sql
-- Items table
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cost DECIMAL(10, 2),
    link TEXT,
    type TEXT CHECK(type IN ('want', 'need')),
    position INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Archive table
CREATE TABLE archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_id INTEGER,
    name TEXT NOT NULL,
    cost DECIMAL(10, 2),
    link TEXT,
    type TEXT,
    archived_reason TEXT CHECK(archived_reason IN ('deleted', 'completed')),
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sessions table
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
```

### API Endpoints

```
POST   /login              # Login with password
POST   /logout             # Logout and clear session
GET    /api/items          # Get all items sorted by position
POST   /api/items          # Create new item
PUT    /api/items/{id}     # Update item
DELETE /api/items/{id}     # Delete item (move to archive)
POST   /api/items/{id}/complete  # Mark item as completed
POST   /api/items/{id}/move      # Move item up/down
GET    /api/export         # Export data as CSV/JSON
POST   /api/import         # Import data from CSV/JSON
GET    /api/archive        # View archived items
```

## Implementation Details

### 1. Authentication Flow
- Single password stored as environment variable
- Login creates session token (UUID)
- Token stored in cookie with 30-day expiration
- All routes except /login require valid session

### 2. List Reordering Logic
- Each item has a position field (1, 2, 3, etc.)
- Moving up: swap positions with previous item
- Moving down: swap positions with next item
- When deleting: resequence all items below

### 3. Import/Export Format
```json
{
  "items": [
    {
      "name": "Nintendo Switch Game",
      "cost": 59.99,
      "link": "https://example.com/game",
      "type": "want",
      "position": 1
    }
  ],
  "exported_at": "2025-01-28T10:00:00Z"
}
```

### 4. Daily Backup Process
- Cron job or Python scheduler runs at 2 AM daily
- Exports full database to JSON
- Stores in `/data/backups/gimmie_backup_YYYY-MM-DD.json`
- Keeps last 30 days of backups

### 5. Mobile Optimization
- Viewport meta tag for proper scaling
- Touch-friendly button sizes (minimum 44x44px)
- Swipe gestures for delete/complete (optional enhancement)
- No hover states, focus on tap interactions

## Docker Configuration

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  gimmie:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - LOGIN_PASSWORD=${LOGIN_PASSWORD}
    restart: unless-stopped
```

## Security Considerations

1. **Environment Variables**:
   - SECRET_KEY: For session encryption
   - LOGIN_PASSWORD: Hashed password for authentication

2. **Input Validation**:
   - Sanitize all user inputs
   - Validate URLs for purchase links
   - Limit string lengths

3. **HTTPS**:
   - Use reverse proxy (nginx) with SSL certificate
   - Force HTTPS redirects

## UI/UX Guidelines

### Login Page
- Single password field
- "Remember me" checkbox (extends session)
- Clean, centered design

### Main List View
- Header with "Gimmie" title and logout button
- "Add Item" button prominently displayed
- Each item card shows:
  - Item name (large, bold)
  - Cost (formatted as currency)
  - Type badge (color-coded)
  - Action buttons (up, down, delete, complete)
- Footer with import/export options

### Mobile Interactions
- Tap to expand item details (show link)
- Long press for quick actions
- Pull-to-refresh for list updates
- Smooth animations for reordering

## Development Phases

### Phase 1: Core Functionality
1. Basic Flask app with SQLite
2. Login system with sessions
3. CRUD operations for items
4. List display and basic styling

### Phase 2: List Management
1. Reordering functionality
2. Archive system
3. Complete/delete actions
4. Position management

### Phase 3: Data Features
1. Import/export functionality
2. Daily backup automation
3. Archive viewing

### Phase 4: Polish
1. Mobile optimization
2. Animations and transitions
3. Error handling
4. Loading states

### Phase 5: Deployment
1. Docker configuration
2. Environment setup
3. Reverse proxy configuration
4. SSL certificate setup

## Testing Checklist

- [ ] Login/logout flow
- [ ] Adding items with all fields
- [ ] Reordering items up/down
- [ ] Deleting items
- [ ] Completing items
- [ ] Import/export functionality
- [ ] Daily backup execution
- [ ] Session expiration
- [ ] Mobile responsiveness
- [ ] Error handling for all endpoints

## Future Enhancements (Post-MVP)

1. Categories for items
2. Price history tracking
3. Shared lists (multiple families)
4. Push notifications for sales
5. Budget tracking
6. Wishlist sharing
7. Dark mode
8. PWA capabilities

## Notes for Implementation

1. Start with Flask for simplicity, can migrate to FastAPI later
2. Use SQLite initially, structure code to allow easy PostgreSQL migration
3. Keep JavaScript minimal - enhance progressively
4. Focus on speed and simplicity over features
5. Test thoroughly on mobile devices
6. Consider using Tailwind CSS for quick, responsive styling

This specification provides a complete blueprint for building the Gimmie app. The focus is on simplicity, mobile usability, and family-friendly features that solve the core problem of forgetting wanted items between paydays.