import os
from datetime import timedelta
from dotenv import load_dotenv
import secrets

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    LOGIN_PASSWORD = os.environ.get('LOGIN_PASSWORD') or 'changeme'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:////app/data/gimmie.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_NAME = 'gimmie_session'
    SESSION_COOKIE_HTTPONLY = True
    # Auto-detect HTTPS from request headers when behind proxy
    SESSION_COOKIE_SECURE = False  # Let ProxyFix handle this dynamically
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size for imports
    
    # CSRF settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens
    WTF_CSRF_CHECK_DEFAULT = True