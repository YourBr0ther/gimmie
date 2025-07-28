#!/bin/bash
set -e

echo "🚀 [$(date '+%Y-%m-%d %H:%M:%S')] Starting Gimmie application..."
echo "📁 [$(date '+%Y-%m-%d %H:%M:%S')] Creating directories..."
mkdir -p /app/data/backups
chmod -R 777 /app/data

echo "🗄️  [$(date '+%Y-%m-%d %H:%M:%S')] Initializing database..."
python3 -c "
import sys
sys.path.insert(0, '/app')
from app import app, db
from models import Item, Archive
import os
os.makedirs('/app/data', exist_ok=True)
os.makedirs('/app/data/backups', exist_ok=True)
with app.app_context():
    db.create_all()
    
    # Migration: Add added_by field to existing items that don't have it
    try:
        # Check if added_by column exists by trying to access it
        db.session.execute(db.text('SELECT added_by FROM items LIMIT 1'))
        
        # If we get here, column exists, update NULL values
        items_without_added_by = Item.query.filter(Item.added_by == None).all()
        for item in items_without_added_by:
            item.added_by = 'Unknown'
        
        archived_without_added_by = Archive.query.filter(Archive.added_by == None).all()
        for item in archived_without_added_by:
            item.added_by = 'Unknown'
        
        db.session.commit()
        print(f'✅ Updated {len(items_without_added_by)} items and {len(archived_without_added_by)} archived items')
    except Exception as e:
        # Column doesn't exist or other error - this is expected for new databases
        print(f'ℹ️  Migration note: {e}')
        print('ℹ️  This is normal for new installations or when schema is being updated')
    
    print('✅ Database created successfully')
"

echo "🌐 [$(date '+%Y-%m-%d %H:%M:%S')] Starting Gunicorn server on port 5010..."
exec gunicorn -b 0.0.0.0:5010 --timeout 300 --workers 2 --log-level info --access-logfile - --error-logfile - app:app