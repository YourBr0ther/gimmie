#!/usr/bin/env python
"""Startup script to initialize the database before running the app"""
import os
from app import app, db, init_scheduler

# Ensure directories exist with absolute paths
os.makedirs('/app/data', exist_ok=True)
os.makedirs('/app/data/backups', exist_ok=True)

# Set proper permissions
os.chmod('/app/data', 0o777)
os.chmod('/app/data/backups', 0o777)

print("Directories created and permissions set")

# Create database tables
try:
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")
except Exception as e:
    print(f"Database initialization failed: {e}")
    # Continue anyway, maybe the tables already exist

# Initialize the scheduler
try:
    scheduler = init_scheduler(app)
    print("Scheduler initialized")
except Exception as e:
    print(f"Scheduler initialization failed: {e}")

# This allows gunicorn to import the app
application = app