"""
Main page routes
"""
from flask import render_template
from flask_login import current_user


def register_routes(app):
    """Register main page routes"""
    
    @app.route('/')
    def index():
        """Home page"""
        return render_template('index.html')
