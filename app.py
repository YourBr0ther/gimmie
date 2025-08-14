import os
import json
import time
import logging
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set up app logger
app.logger.setLevel(logging.INFO)

# Handle reverse proxy headers (for nginx proxy manager)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

db.init_app(app)

# Log startup information
app.logger.info("🚀 Gimmie app starting up...")
app.logger.info("🏷️  Version: 1.0.5-cachebust (duplicate fix + cache busting)")
app.logger.info(f"📊 Environment: {os.environ.get('FLASK_ENV', 'production')}")
app.logger.info(f"🗄️  Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
app.logger.info(f"🔧 Debug mode: {app.debug}")

scheduler = None

# Database should be initialized by entrypoint script

def db_retry(max_retries=3, delay=1):
    """Decorator to retry database operations on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        app.logger.info(f"✅ Database operation succeeded on attempt {attempt + 1} for {func.__name__}")
                    return result
                except (OperationalError, DatabaseError) as e:
                    if attempt == max_retries - 1:
                        app.logger.error(f"❌ Database operation failed after {max_retries} attempts for {func.__name__}: {e}")
                        return jsonify({'error': 'Database temporarily unavailable. Please try again.'}), 503
                    app.logger.warning(f"⚠️  Database operation failed (attempt {attempt + 1}/{max_retries}) for {func.__name__}: {e}")
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
                except Exception as e:
                    app.logger.error(f"❌ Non-database error in {func.__name__}: {e}")
                    # Re-raise non-database errors immediately
                    raise e
            return func(*args, **kwargs)
        return wrapper
    return decorator

def ensure_db_connection():
    """Ensure database connection is available"""
    try:
        db.session.execute(db.text('SELECT 1'))
        app.logger.debug("✅ Database connection check passed")
        return True
    except Exception as e:
        app.logger.error(f"❌ Database connection check failed: {e}")
        return False

# Authentication removed - direct access to app

@app.route('/api/items', methods=['GET', 'POST'])
@db_retry()
def handle_items():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    
    if request.method == 'GET':
        # Health check mode - just return a simple response
        if request.args.get('health'):
            app.logger.debug(f"🩺 Health check from {client_ip}")
            return jsonify({'status': 'ok'})
        
        app.logger.info(f"📋 GET /api/items - Fetching all items for {client_ip}")
        items = Item.query.order_by(Item.position).all()
        app.logger.info(f"📊 Returning {len(items)} items")
        return jsonify([item.to_dict() for item in items])
    
    elif request.method == 'POST':
        data = request.get_json()
        app.logger.info(f"➕ POST /api/items - Creating new item from {client_ip}")
        app.logger.debug(f"📝 Item data: {data}")
        
        # Input validation
        if not data.get('name') or len(data.get('name', '')) > 255:
            app.logger.warning(f"⚠️  Invalid item name from {client_ip}: '{data.get('name')}'")
            return jsonify({'error': 'Name is required and must be less than 255 characters'}), 400
        
        if data.get('type') and data['type'] not in ['want', 'need']:
            app.logger.warning(f"⚠️  Invalid item type from {client_ip}: '{data.get('type')}'")
            return jsonify({'error': 'Type must be either "want" or "need"'}), 400
        
        if data.get('link') and len(data.get('link', '')) > 2000:
            app.logger.warning(f"⚠️  Link too long from {client_ip}: {len(data.get('link'))} chars")
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
        
        app.logger.info(f"✅ Created item '{new_item.name}' (ID: {new_item.id}) at position {new_item.position}")
        return jsonify(new_item.to_dict()), 201

@app.route('/api/items/<int:item_id>', methods=['PUT', 'DELETE'])
@db_retry()
def handle_item(item_id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        app.logger.info(f"✏️  PUT /api/items/{item_id} - Updating item '{item.name}' from {client_ip}")
        
        old_name = item.name
        item.name = data.get('name', item.name)
        item.cost = data.get('cost', item.cost)
        item.link = data.get('link', item.link)
        item.type = data.get('type', item.type)
        
        db.session.commit()
        
        if old_name != item.name:
            app.logger.info(f"📝 Item name changed: '{old_name}' → '{item.name}'")
        app.logger.info(f"✅ Updated item ID {item_id}")
        return jsonify(item.to_dict())
    
    elif request.method == 'DELETE':
        app.logger.info(f"🗑️  DELETE /api/items/{item_id} - Deleting item '{item.name}' from {client_ip}")
        
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
        app.logger.debug(f"🔄 Reordering {len(items_below)} items below position {item.position}")
        for i in items_below:
            i.position -= 1
        
        db.session.delete(item)
        db.session.commit()
        
        app.logger.info(f"✅ Deleted and archived item '{item.name}' (was ID {item_id})")
        return '', 204

@app.route('/api/items/<int:item_id>/complete', methods=['POST'])
@db_retry()
def complete_item(item_id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    item = Item.query.get_or_404(item_id)
    
    app.logger.info(f"✅ POST /api/items/{item_id}/complete - Completing item '{item.name}' from {client_ip}")
    
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
    app.logger.debug(f"🔄 Reordering {len(items_below)} items below position {item.position}")
    for i in items_below:
        i.position -= 1
    
    db.session.delete(item)
    db.session.commit()
    
    app.logger.info(f"🎉 Completed and archived item '{item.name}' (was ID {item_id})")
    return '', 204

@app.route('/api/items/<int:item_id>/move', methods=['POST'])
@db_retry()
def move_item(item_id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    item = Item.query.get_or_404(item_id)
    data = request.get_json()
    direction = data.get('direction')
    
    app.logger.info(f"🔄 POST /api/items/{item_id}/move - Moving item '{item.name}' {direction} from {client_ip}")
    
    if direction == 'up' and item.position > 1:
        other_item = Item.query.filter_by(position=item.position - 1).first()
        if other_item:
            old_pos = item.position
            other_item.position, item.position = item.position, other_item.position
            db.session.commit()
            app.logger.info(f"⬆️  Moved '{item.name}' from position {old_pos} to {item.position}")
    
    elif direction == 'down':
        other_item = Item.query.filter_by(position=item.position + 1).first()
        if other_item:
            old_pos = item.position
            other_item.position, item.position = item.position, other_item.position
            db.session.commit()
            app.logger.info(f"⬇️  Moved '{item.name}' from position {old_pos} to {item.position}")
    else:
        app.logger.debug(f"🚫 Move '{direction}' not possible for item at position {item.position}")
    
    return jsonify(item.to_dict())

@app.route('/api/export', methods=['GET'])
@db_retry()
def export_data():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    app.logger.info(f"💾 GET /api/export - Exporting data for {client_ip}")
    
    items = Item.query.order_by(Item.position).all()
    
    data = {
        'items': [item.to_dict() for item in items],
        'exported_at': datetime.utcnow().isoformat() + 'Z'
    }
    
    app.logger.info(f"📤 Exported {len(items)} items to JSON")
    response = make_response(json.dumps(data, indent=2))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=gimmie_export.json'
    return response

@app.route('/api/import', methods=['POST'])
@db_retry()
def import_data():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    app.logger.info(f"📥 POST /api/import - Importing data from {client_ip}")
    
    file = request.files.get('file')
    if not file:
        app.logger.warning(f"⚠️  Import failed: No file provided from {client_ip}")
        return jsonify({'error': 'No file provided'}), 400
    
    filename = file.filename.lower()
    app.logger.info(f"📁 Importing file: {file.filename}")
    
    try:
        if filename.endswith('.json'):
            data = json.load(file)
            items_data = data.get('items', [])
            
            # Get current item count before deletion
            current_count = Item.query.count()
            app.logger.info(f"🗑️  Clearing {current_count} existing items for import")
            
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
            app.logger.info(f"✅ Import successful: {len(items_data)} items imported")
            return jsonify({'message': 'Import successful', 'items_imported': len(items_data)})
        
        else:
            app.logger.warning(f"⚠️  Import failed: Invalid file type '{filename}' from {client_ip}")
            return jsonify({'error': 'Only JSON files are supported'}), 400
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"❌ Import failed from {client_ip}: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/archive', methods=['GET'])
@db_retry()
def get_archive():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    app.logger.info(f"📂 GET /api/archive - Fetching archived items for {client_ip}")
    
    archived_items = Archive.query.order_by(Archive.archived_at.desc()).all()
    app.logger.info(f"📊 Returning {len(archived_items)} archived items")
    return jsonify([item.to_dict() for item in archived_items])

@app.route('/api/archive/<int:archive_id>/restore', methods=['POST'])
@db_retry()
def restore_item(archive_id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    archived_item = Archive.query.get_or_404(archive_id)
    
    app.logger.info(f"↩️  POST /api/archive/{archive_id}/restore - Restoring '{archived_item.name}' from {client_ip}")
    
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
    
    app.logger.info(f"✅ Restored '{archived_item.name}' to position {restored_item.position} (new ID: {restored_item.id})")
    return jsonify(restored_item.to_dict())

@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')

@app.route('/')
def index():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    user_agent = request.headers.get('User-Agent', 'Unknown')[:100]  # Truncate long user agents
    app.logger.info(f"🏠 GET / - New session from {client_ip} using {user_agent}")
    return render_template('index.html')

if __name__ == '__main__':
    try:
        app.logger.info("🔧 Starting scheduler...")
        scheduler = init_scheduler(app)
        app.logger.info("🚀 Starting Flask development server on port 5010...")
        app.run(debug=True, port=5010)
    except KeyboardInterrupt:
        app.logger.info("🛑 Received interrupt signal, shutting down...")
    finally:
        if scheduler:
            app.logger.info("🔧 Shutting down scheduler...")
            scheduler.shutdown()
        app.logger.info("👋 Gimmie app shut down complete")