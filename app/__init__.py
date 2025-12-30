"""
Flask application initialization module
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config

# Initialize extensions (created outside app factory but not bound to app)
db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_name='default'):
    """
    Application factory function
    :param config_name: Configuration name ('development', 'production', 'default')
    :return: Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Configure Flask-Login
    login_manager.login_view = 'auth.login'  # Redirect to login page when not authenticated
    login_manager.login_message = '请先登录以访问该页面。'
    login_manager.login_message_category = 'warning'
    
    # Register blueprints
    from app.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Register main routes
    from app import main_routes
    main_routes.register_routes(app)
    
    return app


# Flask-Login user loader callback
@login_manager.user_loader
def load_user(user_id):
    """Load user object by user ID"""
    from app.models import User
    return User.query.get(int(user_id))
