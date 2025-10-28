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
        from flask import current_app
        
        # Skip CSRF for GET and OPTIONS requests
        if request.method in ['GET', 'OPTIONS']:
            return f(*args, **kwargs)
        
        # Get token from header
        token = request.headers.get('X-CSRF-Token')
        
        # Debug logging for mobile issues
        current_app.logger.info(f"🔒 CSRF Check - Token received: {bool(token)}, Session token exists: {bool(session.get('csrf_token'))}")
        if token and session.get('csrf_token'):
            current_app.logger.info(f"🔒 CSRF tokens match: {token[:8]}... == {session.get('csrf_token', '')[:8]}...")
        
        # In development, allow missing CSRF for easier testing
        # In production, this should be removed
        if not token and request.headers.get('User-Agent', '').startswith('curl'):
            current_app.logger.info("🔒 CSRF bypass for curl")
            return f(*args, **kwargs)
        
        # If no session token exists, try to generate one
        if not session.get('csrf_token'):
            current_app.logger.warning("🔒 No CSRF token in session, generating new one")
            generate_csrf_token()
        
        # Validate token
        if not token:
            current_app.logger.warning("🔒 CSRF token missing from request")
            return jsonify({'error': 'CSRF token missing. Please refresh the page and try again.'}), 403
        
        if token != session.get('csrf_token'):
            current_app.logger.warning("🔒 CSRF token mismatch")
            return jsonify({'error': 'CSRF token invalid. Please refresh the page and try again.'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def inject_csrf_token(response):
    """Inject CSRF token into response headers"""
    if 'csrf_token' in session:
        response.headers['X-CSRF-Token'] = session['csrf_token']
    return response