import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import session, redirect, url_for, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, Session

def generate_session_token():
    return secrets.token_urlsafe(32)

def create_session():
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    new_session = Session(token=token, expires_at=expires_at)
    db.session.add(new_session)
    db.session.commit()
    
    return token

def validate_session(token):
    if not token:
        return False
    
    session_obj = Session.query.filter_by(token=token).first()
    if not session_obj:
        return False
    
    if datetime.utcnow() > session_obj.expires_at:
        db.session.delete(session_obj)
        db.session.commit()
        return False
    
    return True

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'session_token' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        
        if not validate_session(session.get('session_token')):
            session.pop('session_token', None)
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Session expired'}), 401
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def check_password(password):
    from flask import current_app
    return password == current_app.config['LOGIN_PASSWORD']