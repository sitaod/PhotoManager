"""
JWT-based auth helpers for token issuance and protection.
"""
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Any

import jwt
from flask import current_app, request, jsonify


def generate_auth_token(user_id: int, expires_in: int = 3600) -> str:
    """Generate a signed JWT containing the user_id and an expiration timestamp."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(seconds=expires_in),
    }
    secret = current_app.config.get("SECRET_KEY")
    token = jwt.encode(payload, secret, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def token_required(f: Callable) -> Callable:
    """Decorator to protect routes with Bearer JWT authentication."""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"success": False, "error": "Authorization token missing"}), 401

        token = parts[1]
        try:
            payload = jwt.decode(token, current_app.config.get("SECRET_KEY"), algorithms=["HS256"])
            user_id = payload.get("user_id")
            if user_id is None:
                raise jwt.InvalidTokenError("user_id not present in token")
            # Attach the authenticated user id to the request for downstream handlers
            request.current_user_id = user_id
        except jwt.ExpiredSignatureError:
            return jsonify({"success": False, "error": "Token expired"}), 401
        except jwt.InvalidTokenError as exc:  # Includes DecodeError
            return jsonify({"success": False, "error": f"Invalid token: {exc}"}), 401

        return f(*args, **kwargs)

    return decorated
