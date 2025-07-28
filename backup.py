import os
import json
import shutil
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from models import db, Item

def backup_database(app):
    with app.app_context():
        try:
            backup_dir = '/app/data/backups'
            os.makedirs(backup_dir, exist_ok=True)
            
            items = Item.query.order_by(Item.position).all()
            
            backup_data = {
                'items': [item.to_dict() for item in items],
                'exported_at': datetime.utcnow().isoformat() + 'Z',
                'backup_type': 'automated_daily'
            }
            
            timestamp = datetime.utcnow().strftime('%Y-%m-%d')
            backup_filename = f'gimmie_backup_{timestamp}.json'
            backup_path = os.path.join(backup_dir, backup_filename)
            
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            print(f"Backup created successfully: {backup_filename}")
            
            clean_old_backups(backup_dir)
            
        except Exception as e:
            print(f"Backup failed: {str(e)}")

def clean_old_backups(backup_dir, days_to_keep=30):
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        for filename in os.listdir(backup_dir):
            if filename.startswith('gimmie_backup_') and filename.endswith('.json'):
                file_path = os.path.join(backup_dir, filename)
                file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_modified < cutoff_date:
                    os.remove(file_path)
                    print(f"Deleted old backup: {filename}")
    
    except Exception as e:
        print(f"Error cleaning old backups: {str(e)}")

def init_scheduler(app):
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        func=lambda: backup_database(app),
        trigger="cron",
        hour=2,
        minute=0,
        id='daily_backup',
        name='Daily database backup',
        replace_existing=True
    )
    
    scheduler.start()
    
    print("Backup scheduler initialized - will run daily at 2:00 AM")
    
    return scheduler