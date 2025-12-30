"""
Database initialization script
"""
from app import create_app, db

def init_database():
    """Create all database tables"""
    app = create_app('development')
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")
        print("You can now run 'python run.py' to start the application")

if __name__ == '__main__':
    init_database()
