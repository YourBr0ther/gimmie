"""
Simple CSRF protection for Gimmie app
Since we're not using forms, we'll use a header-based approach
"""
import secrets
from functools import wraps
from flask import session, request, jsonify

def generate_csrf_token():
    """Generate a new CSRF token"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf(f):
    """Decorator to validate CSRF token on state-changing operations"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip CSRF for GET and OPTIONS requests
        if request.method in ['GET', 'OPTIONS']:
            return f(*args, **kwargs)
        
        # Get token from header
        token = request.headers.get('X-CSRF-Token')
        
        # In development, allow missing CSRF for easier testing
        # In production, this should be removed
        if not token and request.headers.get('User-Agent', '').startswith('curl'):
            return f(*args, **kwargs)
        
        # Validate token
        if not token or token != session.get('csrf_token'):
            return jsonify({'error': 'Invalid or missing CSRF token'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def inject_csrf_token(response):
    """Inject CSRF token into response headers"""
    if 'csrf_token' in session:
        response.headers['X-CSRF-Token'] = session['csrf_token']
    return response