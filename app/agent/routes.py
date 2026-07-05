from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.agent import bp
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
    
    try:
        response = run_agent_chat(prompt, current_user.id)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
