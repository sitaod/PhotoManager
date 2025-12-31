"""
Database initialization script
"""
from app import create_app, db
from sqlalchemy import text, create_engine


def init_database():
    """Initialize database: drop old database and create all tables"""
    app = create_app('development')
    
    # Get database connection info
    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    db_name = db_url.split('/')[-1]
    # MySQL connection without database
    mysql_url = db_url.rsplit('/', 1)[0]
    
    with app.app_context():
        try:
            # Create engine for MySQL operations (without database)
            mysql_engine = create_engine(mysql_url + '/mysql')
            connection = mysql_engine.connect()
            connection.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
            connection.commit()
            print(f"[OK] Database '{db_name}' dropped successfully")
            
            # Create new database
            print(f"Creating new database '{db_name}'...")
            connection.execute(text(f"CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"))
            connection.commit()
            print(f"[OK] Database '{db_name}' created successfully")
            connection.close()
            
            # Create all tables with fresh connection
            print("Creating database tables...")
            db.create_all()
            print("[OK] Database tables created successfully!")
            print("\nYou can now run 'python run.py' to start the application")
            
        except Exception as e:
            print(f"[ERROR] {str(e)}")
            raise


if __name__ == '__main__':
    init_database()


if __name__ == '__main__':
    init_database()
