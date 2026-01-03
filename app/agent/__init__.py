from flask import Blueprint

bp = Blueprint('agent', __name__)

from app.agent import routes
