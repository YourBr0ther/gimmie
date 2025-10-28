import os
import json
import time
import logging
import hashlib
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from sqlalchemy.exc import OperationalError, DatabaseError
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, Item, Archive
from auth import login_required, create_session, check_password
from config import Config
from backup import init_scheduler
from validators import validate_item_data, ValidationError
from rate_limiter import create_limiter, RATE_LIMITS
from csrf_protection import generate_csrf_token, validate_csrf, inject_csrf_token

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

# Initialize rate limiter
limiter = create_limiter(app)

# Register CSRF token injection
app.after_request(inject_csrf_token)

# Log startup information
app.logger.info("🚀 Gimmie app starting up...")
app.logger.info("🏷️  Version: 1.1.1 (cache busting + security & performance)")
app.logger.info(f"📊 Environment: {os.environ.get('FLASK_ENV', 'production')}")
app.logger.info(f"🗄️  Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
app.logger.info(f"🔧 Debug mode: {app.debug}")

scheduler = None

# Generate version hash for cache busting
VERSION = "1.1.1"
VERSION_HASH = hashlib.md5(f"{VERSION}-{int(time.time())}".encode()).hexdigest()[:8]

# Template context processor to inject version into templates
@app.context_processor
def inject_version():
    return dict(version=VERSION, version_hash=VERSION_HASH)

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
@limiter.limit(RATE_LIMITS['get_items'], methods=['GET'])
@limiter.limit(RATE_LIMITS['create_item'], methods=['POST'])
@validate_csrf
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
        
        try:
            # Validate and sanitize input
            validated_data = validate_item_data(data)
            
            max_position = db.session.query(db.func.max(Item.position)).scalar() or 0
            
            new_item = Item(
                name=validated_data['name'],
                cost=validated_data['cost'],
                link=validated_data['link'],
                type=validated_data['type'],
                added_by=validated_data['added_by'],
                position=max_position + 1
            )
        except ValidationError as e:
            app.logger.warning(f"⚠️  Validation error from {client_ip}: {str(e)}")
            return jsonify({'error': str(e)}), 400
        
        db.session.add(new_item)
        db.session.commit()
        
        app.logger.info(f"✅ Created item '{new_item.name}' (ID: {new_item.id}) at position {new_item.position}")
        return jsonify(new_item.to_dict()), 201

@app.route('/api/items/<int:item_id>', methods=['PUT', 'DELETE'])
@limiter.limit(RATE_LIMITS['update_item'], methods=['PUT'])
@limiter.limit(RATE_LIMITS['delete_item'], methods=['DELETE'])
@validate_csrf
@db_retry()
def handle_item(item_id):
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        app.logger.info(f"✏️  PUT /api/items/{item_id} - Updating item '{item.name}' from {client_ip}")
        
        try:
            # Validate and sanitize input
            validated_data = validate_item_data({
                'name': data.get('name', item.name),
                'cost': data.get('cost', item.cost),
                'link': data.get('link', item.link),
                'type': data.get('type', item.type),
                'added_by': data.get('added_by', item.added_by)
            })
            
            old_name = item.name
            item.name = validated_data['name']
            item.cost = validated_data['cost']
            item.link = validated_data['link']
            item.type = validated_data['type']
            item.added_by = validated_data['added_by']
            
            db.session.commit()
        except ValidationError as e:
            app.logger.warning(f"⚠️  Validation error from {client_ip}: {str(e)}")
            return jsonify({'error': str(e)}), 400
        
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
        
        # Get all items ordered by position
        all_items = Item.query.order_by(Item.position).all()
        deleted_position = item.position
        
        db.session.delete(item)
        db.session.flush()  # Remove item but don't commit yet
        
        # Reorder remaining items sequentially
        remaining_items = [i for i in all_items if i.id != item_id]
        for idx, i in enumerate(remaining_items):
            i.position = idx + 1
        
        db.session.commit()
        
        app.logger.info(f"✅ Deleted and archived item '{item.name}' (was ID {item_id})")
        return '', 204

@app.route('/api/items/<int:item_id>/complete', methods=['POST'])
@limiter.limit(RATE_LIMITS['complete_item'])
@validate_csrf
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
    
    # Get all items ordered by position
    all_items = Item.query.order_by(Item.position).all()
    
    db.session.delete(item)
    db.session.flush()  # Remove item but don't commit yet
    
    # Reorder remaining items sequentially
    remaining_items = [i for i in all_items if i.id != item_id]
    for idx, i in enumerate(remaining_items):
        i.position = idx + 1
    
    db.session.commit()
    
    app.logger.info(f"🎉 Completed and archived item '{item.name}' (was ID {item_id})")
    return '', 204

@app.route('/api/items/<int:item_id>/move', methods=['POST'])
@limiter.limit(RATE_LIMITS['move_item'])
@validate_csrf
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
@limiter.limit(RATE_LIMITS['export_data'])
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
@limiter.limit(RATE_LIMITS['import_data'])
@validate_csrf
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
            
            # Safety check - require confirmation for destructive import
            if current_count > 0 and not request.form.get('confirm_replace'):
                return jsonify({
                    'error': f'Import would replace {current_count} existing items. Add confirm_replace=true to proceed.',
                    'existing_count': current_count
                }), 400
            
            app.logger.info(f"🗑️  Clearing {current_count} existing items for import")
            
            # Archive existing items before deletion
            existing_items = Item.query.all()
            for item in existing_items:
                archive_item = Archive(
                    original_id=item.id,
                    name=item.name,
                    cost=item.cost,
                    link=item.link,
                    type=item.type,
                    added_by=item.added_by,
                    archived_reason='replaced_by_import'
                )
                db.session.add(archive_item)
            
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
@limiter.limit(RATE_LIMITS['get_archive'])
@db_retry()
def get_archive():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    app.logger.info(f"📂 GET /api/archive - Fetching archived items for {client_ip}")
    
    archived_items = Archive.query.order_by(Archive.archived_at.desc()).all()
    app.logger.info(f"📊 Returning {len(archived_items)} archived items")
    return jsonify([item.to_dict() for item in archived_items])

@app.route('/api/archive/<int:archive_id>/restore', methods=['POST'])
@limiter.limit(RATE_LIMITS['restore_item'])
@validate_csrf
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
    response = make_response(app.send_static_file('manifest.json'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/service-worker.js')
def service_worker():
    response = make_response(app.send_static_file('service-worker.js'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/health', methods=['GET'])
@limiter.limit(RATE_LIMITS['health_check'])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        db.session.execute(db.text('SELECT 1'))
        db_status = 'healthy'
    except Exception:
        db_status = 'unhealthy'
    
    return jsonify({
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'version': VERSION,
        'version_hash': VERSION_HASH,
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded errors"""
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    app.logger.warning(f"⚠️  Rate limit exceeded for {client_ip}")
    return jsonify({
        'error': 'Rate limit exceeded. Please slow down your requests.',
        'retry_after': e.description
    }), 429

@app.errorhandler(400)
def bad_request(e):
    """Handle bad request errors"""
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(404)
def not_found(e):
    """Handle not found errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Resource not found'}), 404
    return render_template('index.html')  # SPA routing

@app.errorhandler(500)
def internal_error(e):
    """Handle internal server errors"""
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    app.logger.error(f"❌ Internal server error for {client_ip}: {str(e)}")
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(DatabaseError)
def database_error(e):
    """Handle database errors"""
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    app.logger.error(f"❌ Database error for {client_ip}: {str(e)}")
    db.session.rollback()
    return jsonify({'error': 'Database temporarily unavailable. Please try again.'}), 503

@app.errorhandler(Exception)
def handle_exception(e):
    """Handle unexpected exceptions"""
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    app.logger.error(f"❌ Unexpected error for {client_ip}: {str(e)}", exc_info=True)
    db.session.rollback()
    return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/')
def index():
    client_ip = request.environ.get('HTTP_X_REAL_IP', request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr))
    user_agent = request.headers.get('User-Agent', 'Unknown')[:100]  # Truncate long user agents
    app.logger.info(f"🏠 GET / - New session from {client_ip} using {user_agent}")
    
    # Generate CSRF token for the session
    generate_csrf_token()
    
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