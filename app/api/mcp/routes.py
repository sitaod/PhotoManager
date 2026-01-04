"""MCP-facing APIs secured by JWT (JSON-RPC 2.0 compliant)."""
import json
from datetime import datetime
from typing import List, Any, Dict

from flask import request, jsonify, url_for, Response
from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload

from app.api import api_bp
from app.models import Image, Tag
from app.utils.auth import token_required


def _perform_search(user_id: int, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Internal helper to execute the search logic."""
    query = Image.query.filter(Image.user_id == user_id)

    # Location fuzzy match
    location = str(params.get('location', '') or '').strip()
    if location:
        query = query.filter(Image.shoot_location.ilike(f"%{location}%"))

    # Tags union search
    tags: List[str] = params.get('tags') or []
    cleaned_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    if cleaned_tags:
        tag_filters = [Tag.tag_content.ilike(f"%{tag}%") for tag in cleaned_tags]
        query = query.join(Tag).filter(or_(*tag_filters)).distinct()

    # Year filter
    year_raw = str(params.get('year', '') or '').strip()
    if year_raw:
        try:
            year_int = int(year_raw)
            start_dt = datetime(year_int, 1, 1)
            end_dt = datetime(year_int + 1, 1, 1)
            
            # Match either shoot_time in range OR tag content equals "YYYY年"
            year_tag = f"{year_int}年"
            query = query.filter(
                or_(
                    and_(Image.shoot_time >= start_dt, Image.shoot_time < end_dt),
                    Image.tags.any(Tag.tag_content == year_tag)
                )
            )
        except ValueError:
            pass

    images = (
        query.options(joinedload(Image.tags))
        .order_by(Image.upload_time.desc())
        .all()
    )

    results = []
    for image in images:
        thumb_url = url_for('static', filename=image.thumbnail_path, _external=False)
        results.append({
            'id': image.id,
            'thumbnail_url': thumb_url,
            'tags': [tag.tag_content for tag in image.tags],
            'shoot_location': image.shoot_location,
            'shoot_time': image.shoot_time.isoformat() if image.shoot_time else None,
        })
    return results


@api_bp.route('/mcp', methods=['POST', 'GET'])
@token_required
def handle_mcp_request():
    """
    MCP Endpoint handling JSON-RPC 2.0 requests.
    Supports: initialize, tools/list, tools/call
    """
    # Handle GET for SSE stream (optional in this stateless impl, but good for compliance check)
    if request.method == 'GET':
        # For now, we don't support full SSE streaming in this simple Flask app without async/queue
        # But we can return 405 or a basic stream if needed.
        # The spec says: "The server MUST either return Content-Type: text/event-stream ... or else return HTTP 405"
        return "SSE not implemented in this demo", 405

    # Handle POST
    payload = request.get_json(silent=True) or {}
    
    # Basic JSON-RPC validation
    if payload.get('jsonrpc') != '2.0':
        return jsonify({
            "jsonrpc": "2.0", 
            "error": {"code": -32600, "message": "Invalid Request"}, 
            "id": payload.get('id')
        }), 400

    method = payload.get('method')
    msg_id = payload.get('id')
    params = payload.get('params', {})
    user_id = getattr(request, 'current_user_id', None)

    # 1. Initialize
    if method == 'initialize':
        return jsonify({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "PhotoManagerMCP",
                    "version": "1.0.0"
                }
            }
        })

    # 2. Initialized Notification
    if method == 'notifications/initialized':
        return '', 202

    # 3. List Tools
    if method == 'tools/list':
        return jsonify({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [{
                    "name": "search_images",
                    "description": "Search for images based on location, tags, and year.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "Location name (fuzzy match)"},
                            "tags": {
                                "type": "array", 
                                "items": {"type": "string"},
                                "description": "List of tags to match"
                            },
                            "year": {"type": "string", "description": "Year of the photo (e.g. '2024')"}
                        }
                    }
                }]
            }
        })

    # 4. Call Tool
    if method == 'tools/call':
        tool_name = params.get('name')
        args = params.get('arguments', {})
        
        if tool_name == 'search_images':
            try:
                results = _perform_search(user_id, args)
                return jsonify({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": json.dumps(results, ensure_ascii=False)
                        }]
                    }
                })
            except Exception as e:
                return jsonify({
                    "jsonrpc": "2.0", 
                    "error": {"code": -32000, "message": str(e)}, 
                    "id": msg_id
                }), 500
        
        return jsonify({
            "jsonrpc": "2.0", 
            "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}, 
            "id": msg_id
        }), 404

    # Unknown method
    return jsonify({
        "jsonrpc": "2.0", 
        "error": {"code": -32601, "message": f"Method not found: {method}"}, 
        "id": msg_id
    }), 404
