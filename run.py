"""
Application startup entry point
"""
from app import create_app, db

# Create Flask application instance
app = create_app('development')


@app.shell_context_processor
def make_shell_context():
    """Add context for Flask Shell"""
    from app.models import User
    return {
        'db': db,
        'User': User
    }


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
