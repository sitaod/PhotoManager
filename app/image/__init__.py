"""
Image blueprint initialization
"""
from flask import Blueprint

image_bp = Blueprint('image', __name__)

from app.image import routes
