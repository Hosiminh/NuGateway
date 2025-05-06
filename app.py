from flask import Flask, render_template, jsonify
import json
import os

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

@app.route('/sensors')
def sensors():
    try:
        with open('sensors.json') as f:
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
        # varsayılan ayarlar
        return jsonify({
            "gateway_name": "nuGateway",
            "serial_port": "/dev/ttyUSB0",
            "baudrate": 9600,
            "interval": 10
        })

@app.route("/save-settings", methods=["POST"])
def save_settings():
    data = request.get_json()
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
