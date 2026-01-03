from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.agent import bp
from app.utils.auth import generate_auth_token
from app.services.agent_service import run_agent_chat

@bp.route('/chat')
@login_required
def chat():
    return render_template('agent/chat.html')

@bp.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    data = request.get_json()
    prompt = data.get('prompt')
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    # Generate a short-lived token for this request context to allow the agent to call MCP
    token = generate_auth_token(current_user.id, expires_in=300)
    
    try:
        response = run_agent_chat(prompt, token)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
