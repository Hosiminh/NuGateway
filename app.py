from flask import Flask, render_template, jsonify, request
import json
import os
import socket
import uuid
import serial.tools.list_ports

app = Flask(__name__)

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

@app.route("/sensors")
def sensors():
    try:
        with open("sensors.json") as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify([])

SETTINGS_FILE = "gateway_settings.json"

@app.route("/get-settings")
def get_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return jsonify(json.load(f))
    else:
        return jsonify({
            "gateway_name": "nuGateway",
            "serial_port": "/dev/ttyUSB0",
            "baudrate": 9600,
            "interval": 10,
            "mac_address": get_mac_address(),
            "ip_address": get_ip_address(),
            "location": "",
            "data_bits": 8,
            "parity": "N",
            "stop_bits": 1
        })

@app.route("/save-settings", methods=["POST"])
def save_settings():
    data = request.get_json()
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return jsonify({"status": "ok"})

@app.route("/serial-ports")
def list_serial_ports():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    return jsonify({"ports": ports})

@app.route("/network-info")
def get_network_info():
    ip = get_ip_address()
    mac = get_mac_address()
    return jsonify({"ip": ip, "mac": mac})

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"

def get_mac_address():
    mac_num = hex(uuid.getnode()).replace("0x", "").upper()
    mac = ":".join(mac_num[i:i+2] for i in range(0, 12, 2))
    return mac

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
