#!/usr/bin/env python3
"""
Database migration script for Gimmie app
Safely applies schema changes to production databases
"""
import os
import sys
import json
from datetime import datetime
from sqlalchemy import inspect, text
from app import app, db
from models import Item, Archive, Session

class DatabaseMigrator:
    def __init__(self):
        self.inspector = None
        self.migrations_applied = []
        
    def backup_before_migration(self):
        """Create a backup before applying migrations"""
        backup_dir = '/app/data/backups'
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
        backup_file = os.path.join(backup_dir, f'pre_migration_backup_{timestamp}.json')
        
        # Export all data
        items = Item.query.order_by(Item.position).all()
        archives = Archive.query.all()
        
        backup_data = {
            'timestamp': timestamp,
            'type': 'pre_migration_backup',
            'items': [item.to_dict() for item in items],
            'archives': [archive.to_dict() for archive in archives]
        }
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        print(f"✅ Created backup: {backup_file}")
        return backup_file
    
    def check_column_exists(self, table_name, column_name):
        """Check if a column exists in a table"""
        columns = self.inspector.get_columns(table_name)
        return any(col['name'] == column_name for col in columns)
    
    def check_table_exists(self, table_name):
        """Check if a table exists"""
        return self.inspector.has_table(table_name)
    
    def migrate_add_missing_columns(self):
        """Add any missing columns to existing tables"""
        migrations = []
        
        # Check Items table
        if self.check_table_exists('items'):
            if not self.check_column_exists('items', 'added_by'):
                db.session.execute(text(
                    "ALTER TABLE items ADD COLUMN added_by VARCHAR(100) DEFAULT 'Unknown'"
                ))
                migrations.append("Added 'added_by' column to items table")
            
            if not self.check_column_exists('items', 'position'):
                # Add position column and populate it
                db.session.execute(text(
                    "ALTER TABLE items ADD COLUMN position INTEGER"
                ))
                # Set positions based on creation order
                items = Item.query.order_by(Item.created_at).all()
                for idx, item in enumerate(items):
                    item.position = idx + 1
                db.session.commit()
                migrations.append("Added 'position' column to items table")
        
        # Check Archive table
        if self.check_table_exists('archive'):
            if not self.check_column_exists('archive', 'added_by'):
                db.session.execute(text(
                    "ALTER TABLE archive ADD COLUMN added_by VARCHAR(100)"
                ))
                migrations.append("Added 'added_by' column to archive table")
        
        return migrations
    
    def fix_position_gaps(self):
        """Fix any gaps in item positions"""
        items = Item.query.order_by(Item.position).all()
        
        # Check for gaps or duplicates
        needs_fix = False
        positions = [item.position for item in items]
        
        if positions:
            # Check if positions are sequential starting from 1
            expected = list(range(1, len(positions) + 1))
            if positions != expected:
                needs_fix = True
        
        if needs_fix:
            # Reassign positions sequentially
            for idx, item in enumerate(items):
                item.position = idx + 1
            db.session.commit()
            return ["Fixed position gaps in items table"]
        
        return []
    
    def run_migrations(self):
        """Run all migrations"""
        print("🔧 Starting database migrations...")
        
        with app.app_context():
            self.inspector = inspect(db.engine)
            
            # Create backup first
            backup_file = self.backup_before_migration()
            
            try:
                # Create all tables if they don't exist
                db.create_all()
                print("✅ Ensured all tables exist")
                
                # Run specific migrations
                migrations = []
                migrations.extend(self.migrate_add_missing_columns())
                migrations.extend(self.fix_position_gaps())
                
                # Update NULL values
                Item.query.filter(Item.added_by == None).update({'added_by': 'Unknown'})
                Archive.query.filter(Archive.added_by == None).update({'added_by': 'Unknown'})
                
                db.session.commit()
                
                if migrations:
                    print("\n✅ Applied migrations:")
                    for migration in migrations:
                        print(f"  - {migration}")
                else:
                    print("✅ No migrations needed - database is up to date")
                
                return True
                
            except Exception as e:
                print(f"\n❌ Migration failed: {e}")
                print(f"💾 Backup available at: {backup_file}")
                db.session.rollback()
                return False

if __name__ == "__main__":
    migrator = DatabaseMigrator()
    success = migrator.run_migrations()
    sys.exit(0 if success else 1)