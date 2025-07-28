import os
import json
import time
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from sqlalchemy.exc import OperationalError, DatabaseError
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, Item, Archive
from auth import login_required, create_session, check_password
from config import Config
from backup import init_scheduler

app = Flask(__name__)
app.config.from_object(Config)

# Handle reverse proxy headers (for nginx proxy manager)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

db.init_app(app)

scheduler = None

# Database should be initialized by entrypoint script

def db_retry(max_retries=3, delay=1):
    """Decorator to retry database operations on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DatabaseError) as e:
                    if attempt == max_retries - 1:
                        print(f"Database operation failed after {max_retries} attempts: {e}")
                        return jsonify({'error': 'Database temporarily unavailable. Please try again.'}), 503
                    print(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
                except Exception as e:
                    # Re-raise non-database errors immediately
                    raise e
            return func(*args, **kwargs)
        return wrapper
    return decorator

def ensure_db_connection():
    """Ensure database connection is available"""
    try:
        db.session.execute(db.text('SELECT 1'))
        return True
    except Exception as e:
        print(f"Database connection check failed: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

# Authentication removed - direct access to app

@app.route('/api/items', methods=['GET', 'POST'])
@db_retry()
def handle_items():
    if request.method == 'GET':
        # Health check mode - just return a simple response
        if request.args.get('health'):
            return jsonify({'status': 'ok'})
        
        items = Item.query.order_by(Item.position).all()
        return jsonify([item.to_dict() for item in items])
    
    elif request.method == 'POST':
        data = request.get_json()
        
        # Input validation
        if not data.get('name') or len(data.get('name', '')) > 255:
            return jsonify({'error': 'Name is required and must be less than 255 characters'}), 400
        
        if data.get('type') and data['type'] not in ['want', 'need']:
            return jsonify({'error': 'Type must be either "want" or "need"'}), 400
        
        if data.get('link') and len(data.get('link', '')) > 2000:
            return jsonify({'error': 'Link must be less than 2000 characters'}), 400
        
        max_position = db.session.query(db.func.max(Item.position)).scalar() or 0
        
        new_item = Item(
            name=data['name'][:255],
            cost=data.get('cost'),
            link=data.get('link'),
            type=data.get('type', 'want'),
            added_by=data.get('added_by', 'Unknown'),
            position=max_position + 1
        )
        
        db.session.add(new_item)
        db.session.commit()
        
        return jsonify(new_item.to_dict()), 201

@app.route('/api/items/<int:item_id>', methods=['PUT', 'DELETE'])
@db_retry()
def handle_item(item_id):
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        item.name = data.get('name', item.name)
        item.cost = data.get('cost', item.cost)
        item.link = data.get('link', item.link)
        item.type = data.get('type', item.type)
        db.session.commit()
        return jsonify(item.to_dict())
    
    elif request.method == 'DELETE':
        archive_item = Archive(
            original_id=item.id,
            name=item.name,
            cost=item.cost,
            link=item.link,
            type=item.type,
            added_by=item.added_by,
            archived_reason='deleted'
        )
        db.session.add(archive_item)
        
        items_below = Item.query.filter(Item.position > item.position).all()
        for i in items_below:
            i.position -= 1
        
        db.session.delete(item)
        db.session.commit()
        
        return '', 204

@app.route('/api/items/<int:item_id>/complete', methods=['POST'])
@db_retry()
def complete_item(item_id):
    item = Item.query.get_or_404(item_id)
    
    archive_item = Archive(
        original_id=item.id,
        name=item.name,
        cost=item.cost,
        link=item.link,
        type=item.type,
        added_by=item.added_by,
        archived_reason='completed'
    )
    db.session.add(archive_item)
    
    items_below = Item.query.filter(Item.position > item.position).all()
    for i in items_below:
        i.position -= 1
    
    db.session.delete(item)
    db.session.commit()
    
    return '', 204

@app.route('/api/items/<int:item_id>/move', methods=['POST'])
@db_retry()
def move_item(item_id):
    item = Item.query.get_or_404(item_id)
    data = request.get_json()
    direction = data.get('direction')
    
    if direction == 'up' and item.position > 1:
        other_item = Item.query.filter_by(position=item.position - 1).first()
        if other_item:
            other_item.position, item.position = item.position, other_item.position
            db.session.commit()
    
    elif direction == 'down':
        other_item = Item.query.filter_by(position=item.position + 1).first()
        if other_item:
            other_item.position, item.position = item.position, other_item.position
            db.session.commit()
    
    return jsonify(item.to_dict())

@app.route('/api/export', methods=['GET'])
@db_retry()
def export_data():
    items = Item.query.order_by(Item.position).all()
    
    data = {
        'items': [item.to_dict() for item in items],
        'exported_at': datetime.utcnow().isoformat() + 'Z'
    }
    response = make_response(json.dumps(data, indent=2))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=gimmie_export.json'
    return response

@app.route('/api/import', methods=['POST'])
@db_retry()
def import_data():
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file provided'}), 400
    
    filename = file.filename.lower()
    
    try:
        if filename.endswith('.json'):
            data = json.load(file)
            items_data = data.get('items', [])
            
            Item.query.delete()
            
            for idx, item_data in enumerate(items_data):
                item = Item(
                    name=item_data['name'],
                    cost=item_data.get('cost'),
                    link=item_data.get('link'),
                    type=item_data.get('type', 'want'),
                    added_by=item_data.get('added_by', 'Unknown'),
                    position=idx + 1
                )
                db.session.add(item)
            
            db.session.commit()
            return jsonify({'message': 'Import successful', 'items_imported': len(items_data)})
        
        else:
            return jsonify({'error': 'Only JSON files are supported'}), 400
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/archive', methods=['GET'])
@db_retry()
def get_archive():
    archived_items = Archive.query.order_by(Archive.archived_at.desc()).all()
    return jsonify([item.to_dict() for item in archived_items])

@app.route('/api/archive/<int:archive_id>/restore', methods=['POST'])
@db_retry()
def restore_item(archive_id):
    archived_item = Archive.query.get_or_404(archive_id)
    
    # Get the highest position to add item at the end
    max_position = db.session.query(db.func.max(Item.position)).scalar() or 0
    
    # Create new item from archived data
    restored_item = Item(
        name=archived_item.name,
        cost=archived_item.cost,
        link=archived_item.link,
        type=archived_item.type,
        added_by=archived_item.added_by,
        position=max_position + 1
    )
    
    db.session.add(restored_item)
    
    # Remove from archive
    db.session.delete(archived_item)
    
    db.session.commit()
    
    return jsonify(restored_item.to_dict())

@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')

if __name__ == '__main__':
    try:
        scheduler = init_scheduler(app)
        app.run(debug=True, port=5010)
    finally:
        if scheduler:
            scheduler.shutdown()