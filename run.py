"""
Application startup entry point
"""
from app import create_app, db
from app.services.semantic_search_service import start_semantic_index_worker

# Create Flask application instance
app = create_app('development')
start_semantic_index_worker(app)


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
