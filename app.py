from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import json
import os
import socket
import uuid
import serial.tools.list_ports
import logging
from datetime import datetime
from config import config_manager
from logger import setup_logging
from relay_control import relay_controller, manual_control, get_relay_states
from alarm_system import AlarmSystem

# Setup logging
setup_logging(
    log_level=config_manager.get('log_level', 'INFO'),
    log_file=config_manager.get('log_file', 'nugateway.log')
)
logger = logging.getLogger(__name__)

# Flask app initialization
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*")

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Initialize alarm system
alarm_system = AlarmSystem(config_manager)

# Authentication decorator
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not config_manager.get('enable_auth', False):
            return f(*args, **kwargs)
        
        # Check for API token in header
        token = request.headers.get('X-API-Token')
        if token and token == config_manager.get('api_token', ''):
            return f(*args, **kwargs)
        
        # Check for session
        if 'authenticated' in session and session['authenticated']:
            return f(*args, **kwargs)
        
        return jsonify({"error": "Unauthorized"}), 401
    
    return decorated

# === Routes ===

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/devices")
def devices():
    return render_template("devices.html")

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/alarms")
def alarms_page():
    return render_template("alarms.html")

# === API Endpoints ===

@app.route('/api/sensors')
@limiter.limit("60 per minute")
@requires_auth
def api_sensors():
    """Get current sensor data"""
    try:
        with open('sensors.json') as f:
            data = json.load(f)
            data['timestamp'] = datetime.now().isoformat()
            return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "No sensor data available"}), 404
    except Exception as e:
        logger.error(f"Error reading sensors: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/relays')
@requires_auth
def api_relays():
    """Get current relay states"""
    return jsonify(get_relay_states())

@app.route('/api/relay/<name>', methods=['POST'])
@requires_auth
def api_relay_control(name):
    """Control individual relay"""
    try:
        data = request.get_json()
        state = data.get('state', False)
        
        if manual_control(name, state):
            # Emit update via WebSocket
            socketio.emit('relay_update', {
                'name': name,
                'state': state
            })
            return jsonify({"status": "ok", "relay": name, "state": state})
        else:
            return jsonify({"error": "Failed to control relay"}), 500
            
    except Exception as e:
        logger.error(f"Relay control error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/alarms/active')
@requires_auth
def api_active_alarms():
    """Get active alarms"""
    return jsonify(alarm_system.get_active_alarms())

@app.route('/api/alarms/history')
@requires_auth
def api_alarm_history():
    """Get alarm history"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify(alarm_system.get_alarm_history(limit))

@app.route('/api/alarms/clear', methods=['POST'])
@requires_auth
def api_clear_alarms():
    """Clear alarms"""
    data = request.get_json()
    sensor = data.get('sensor')
    alarm_system.clear_alarms(sensor)
    return jsonify({"status": "ok"})

@app.route("/api/settings", methods=['GET'])
@requires_auth
def api_get_settings():
    """Get current settings"""
    return jsonify(config_manager.to_dict())

@app.route("/api/settings", methods=['POST'])
@requires_auth
def api_save_settings():
    """Save settings"""
    try:
        data = request.get_json()
        
        # Update config
        for key, value in data.items():
            config_manager.set(key, value)
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Settings save error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/network-info")
def api_network_info():
    """Get network information"""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff)
                        for ele in range(0, 2*6, 8)][::-1])
        return jsonify({
            "hostname": hostname,
            "ip": ip,
            "mac": mac
        })
    except Exception as e:
        logger.error(f"Network info error: {e}")
        return jsonify({
            "hostname": "unknown",
            "ip": "0.0.0.0",
            "mac": "00:00:00:00:00:00"
        })

@app.route("/api/serial-ports")
def api_serial_ports():
    """List available serial ports"""
    try:
        ports = [port.device for port in serial.tools.list_ports.comports()]
        return jsonify({"ports": ports})
    except Exception as e:
        logger.error(f"Serial ports error: {e}")
        return jsonify({"ports": []})

@app.route("/api/stats")
@requires_auth
def api_stats():
    """Get system statistics"""
    try:
        # Read sensor data history from log file
        stats = {
            "uptime": "N/A",
            "total_readings": 0,
            "active_alarms": len(alarm_system.get_active_alarms()),
            "mqtt_connected": False,  # TODO: Get from MQTT client
            "last_update": datetime.now().isoformat()
        }
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500

# === Authentication ===

@app.route("/api/login", methods=['POST'])
@limiter.limit("5 per minute")
def api_login():
    """Login endpoint"""
    if not config_manager.get('enable_auth', False):
        return jsonify({"error": "Authentication not enabled"}), 400
    
    data = request.get_json()
    token = data.get('token', '')
    
    if token == config_manager.get('api_token', ''):
        session['authenticated'] = True
        return jsonify({"status": "ok", "message": "Authenticated"})
    else:
        return jsonify({"error": "Invalid token"}), 401

@app.route("/api/logout", methods=['POST'])
def api_logout():
    """Logout endpoint"""
    session.pop('authenticated', None)
    return jsonify({"status": "ok", "message": "Logged out"})

# === WebSocket Events ===

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to nuGateway'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('request_update')
def handle_update_request():
    """Handle real-time data request"""
    try:
        with open('sensors.json') as f:
            data = json.load(f)
            data['timestamp'] = datetime.now().isoformat()
            emit('sensor_update', data)
    except Exception as e:
        logger.error(f"Update request error: {e}")

# Background task to broadcast sensor updates
def background_sensor_broadcast():
    """Broadcast sensor data to all connected clients"""
    import time
    while True:
        try:
            socketio.sleep(5)  # Update every 5 seconds
            with open('sensors.json') as f:
                data = json.load(f)
                data['timestamp'] = datetime.now().isoformat()
                socketio.emit('sensor_update', data, broadcast=True)
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            socketio.sleep(5)

# === Error Handlers ===

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded"}), 429

# === Main ===

if __name__ == "__main__":
    logger.info("🚀 nuGateway Flask app starting...")
    logger.info(f"Authentication: {'Enabled' if config_manager.get('enable_auth', False) else 'Disabled'}")
    
    # Start background broadcast thread
    socketio.start_background_task(background_sensor_broadcast)
    
    # Run app
    socketio.run(
        app,
        debug=True,
        host="0.0.0.0",
        port=5000,
        allow_unsafe_werkzeug=True
    )