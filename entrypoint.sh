#!/bin/bash
set -e

echo "🚀 [$(date '+%Y-%m-%d %H:%M:%S')] Starting Gimmie application..."
echo "🏷️  [$(date '+%Y-%m-%d %H:%M:%S')] Version: 1.1.1 (cache busting + security & performance)"
echo "📁 [$(date '+%Y-%m-%d %H:%M:%S')] Creating directories..."
mkdir -p /app/data/backups
chmod -R 777 /app/data

echo "🗄️  [$(date '+%Y-%m-%d %H:%M:%S')] Running database migrations..."
if [ -f /app/migrate.py ]; then
    python3 /app/migrate.py
    if [ $? -eq 0 ]; then
        echo "✅ [$(date '+%Y-%m-%d %H:%M:%S')] Database migrations completed successfully"
    else
        echo "❌ [$(date '+%Y-%m-%d %H:%M:%S')] Database migrations failed, but continuing..."
    fi
else
    echo "⚠️  [$(date '+%Y-%m-%d %H:%M:%S')] migrate.py not found, using basic initialization"
    python3 -c "
import sys
sys.path.insert(0, '/app')
from app import app, db
import os
os.makedirs('/app/data', exist_ok=True)
os.makedirs('/app/data/backups', exist_ok=True)
with app.app_context():
    db.create_all()
    print('✅ Database tables created')
"
fi

echo "🌐 [$(date '+%Y-%m-%d %H:%M:%S')] Starting Gunicorn server on port 5010..."
exec gunicorn -b 0.0.0.0:5010 --timeout 300 --workers 2 --log-level info --access-logfile - --error-logfile - app:app