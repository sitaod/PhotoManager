from flask import Blueprint

api_bp = Blueprint('api', __name__)

# Import routes to register endpoints
from app.api.mcp import routes  # noqa: E402,F401
