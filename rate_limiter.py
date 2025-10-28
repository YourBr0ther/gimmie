"""
Rate limiting configuration for Gimmie app
"""
from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

def get_real_ip():
    """Get the real IP address, considering proxy headers"""
    # Check for proxy headers in order of preference
    real_ip = request.environ.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip
    
    forwarded_for = request.environ.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        # Take the first IP if there's a chain
        return forwarded_for.split(',')[0].strip()
    
    # Fallback to remote_addr
    return request.remote_addr or '127.0.0.1'

def create_limiter(app):
    """Create and configure the rate limiter"""
    limiter = Limiter(
        app=app,
        key_func=get_real_ip,
        default_limits=["1000 per hour"],  # Global default
        storage_uri="memory://",
        swallow_errors=True,  # Don't break the app if rate limiting fails
    )
    
    return limiter

# Rate limit configurations for different endpoints
RATE_LIMITS = {
    # Strict limits for data modification
    'create_item': '30 per minute',
    'update_item': '60 per minute',
    'delete_item': '30 per minute',
    'complete_item': '30 per minute',
    'move_item': '120 per minute',
    
    # Moderate limits for data access
    'get_items': '300 per minute',
    'get_archive': '60 per minute',
    
    # Strict limits for bulk operations
    'import_data': '5 per minute',
    'export_data': '30 per minute',
    
    # Very strict for restore operations
    'restore_item': '20 per minute',
    
    # Health check can be more frequent
    'health_check': '600 per minute',
}