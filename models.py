from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    cost = db.Column(db.Numeric(10, 2))
    link = db.Column(db.Text)
    type = db.Column(db.String(10), nullable=False, default='want', info={'check_constraint': "type IN ('want', 'need')"})
    added_by = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'cost': float(self.cost) if self.cost else None,
            'link': self.link,
            'type': self.type,
            'added_by': self.added_by,
            'position': self.position,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Archive(db.Model):
    __tablename__ = 'archive'
    
    id = db.Column(db.Integer, primary_key=True)
    original_id = db.Column(db.Integer)
    name = db.Column(db.String(255), nullable=False)
    cost = db.Column(db.Numeric(10, 2))
    link = db.Column(db.Text)
    type = db.Column(db.String(10))
    added_by = db.Column(db.String(100))
    archived_reason = db.Column(db.String(20), nullable=False, info={'check_constraint': "archived_reason IN ('deleted', 'completed')"})
    archived_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'original_id': self.original_id,
            'name': self.name,
            'cost': float(self.cost) if self.cost else None,
            'link': self.link,
            'type': self.type,
            'added_by': self.added_by,
            'archived_reason': self.archived_reason,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None
        }

class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)