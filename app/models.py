"""
Database models definition
"""
from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    """
    User model
    Strictly corresponds to the SQL table structure in the design document
    """
    __tablename__ = 'user'
    
    # Field definitions
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, nullable=False)
    username = db.Column(db.String(50), nullable=False, unique=True, index=True)
    email = db.Column(db.String(100), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    register_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """Set password (automatically hashed)"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    # Flask-Login required properties
    def get_id(self):
        """Return user's unique identifier"""
        return str(self.id)


class Image(db.Model):
    """
    Image model
    Strictly corresponds to the SQL table structure in the design document
    """
    __tablename__ = 'image'
    
    # Field definitions
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    image_path = db.Column(db.String(512), nullable=False)
    thumbnail_path = db.Column(db.String(512), nullable=False)
    upload_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    shoot_time = db.Column(db.DateTime, nullable=True)
    shoot_location = db.Column(db.String(200), nullable=True)
    resolution = db.Column(db.String(50), nullable=True)
    
    # Foreign key relationship
    user = db.relationship('User', backref=db.backref('images', cascade='all, delete-orphan'))
    tags = db.relationship('Tag', backref=db.backref('image', lazy=True), cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Image {self.id} of user {self.user_id}>'


class Tag(db.Model):
    """
    Tag model for image classification
    Strictly corresponds to the SQL table structure in the design document
    """
    __tablename__ = 'tag'
    
    # Field definitions
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, nullable=False)
    image_id = db.Column(db.BigInteger, db.ForeignKey('image.id', ondelete='CASCADE'), nullable=False, index=True)
    tag_content = db.Column(db.String(50), nullable=False, index=True)
    
    def __repr__(self):
        return f'<Tag {self.tag_content}>'
