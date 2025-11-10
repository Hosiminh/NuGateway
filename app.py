"""
Nu Gateway - Flask Web Server
Sadece web arayüzü ve API endpoint'leri
Modbus okuma: modbus_reader.py tarafından yapılıyor
"""

from flask import Flask, render_template, jsonify, send_from_directory, request
import json
import os
from datetime import datetime

app = Flask(__name__)

# ========================================
# VERI PAYLAŞIMI (modbus_reader.py ile)
# ========================================

# Modbus verilerini saklamak için (modbus_reader.py tarafından doldurulacak)
MODBUS_DATA_FILE = 'modbus_data.json'
modbus_data = {}

def load_modbus_data():
    """modbus_data.json dosyasından veriyi yükle"""
    global modbus_data
    try:
        if os.path.exists(MODBUS_DATA_FILE):
            with open(MODBUS_DATA_FILE, 'r') as f:
                modbus_data = json.load(f)
        return modbus_data
    except Exception as e:
        print(f"⚠️ Modbus data yüklenemedi: {e}")
        return {}

# ========================================
# STATIC DOSYALAR ve PARTIALS
# ========================================

@app.route('/statics/<path:filename>')
def statics(filename):
    """Static dosyalar (CSS, JS, vs.)"""
    return send_from_directory('statics', filename)

@app.route('/templates/partials/<path:filename>')
def partials(filename):
    """Partial template'ler (footer.html vs.)"""
    return send_from_directory('templates/partials', filename)

# ========================================
# WEB SAYFALARI
# ========================================

@app.route('/')
@app.route('/dashboard')
def dashboard():
    """Ana sayfa - Dashboard"""
    return render_template('dashboard.html')

@app.route('/devices')
def devices():
    """Cihazlar listesi"""
    return render_template('devices.html')

@app.route('/mppt_control')
def mppt_control():
    """MPPT Kontrol sayfası"""
    return render_template('mppt_control.html')

@app.route('/relay_control')
def relay_control():
    """Röle Kontrol sayfası"""
    return render_template('relay_control.html')

@app.route('/automation')
def automation():
    """Alarm & Otomasyon sayfası"""
    return render_template('automation.html')

@app.route('/settings')
def settings():
    """Ayarlar sayfası"""
    return render_template('settings.html')

# ========================================
# API ENDPOINT'LERİ - VERI OKUMA
# ========================================

@app.route('/api/modbus/data')
def get_modbus_data():
    """Tüm Modbus verilerini döndür"""
    data = load_modbus_data()
    return jsonify(data)

@app.route('/api/modbus/ldr')
def get_ldr_data():
    """LDR sensör verisi"""
    data = load_modbus_data()
    return jsonify({
        'light_level': data.get('light_level', None)
    })

@app.route('/api/modbus/env')
def get_env_data():
    """Çevre sensörü verisi"""
    data = load_modbus_data()
    return jsonify({
        'temperature': data.get('temperature', None),
        'humidity': data.get('humidity', None),
        'co2': data.get('co2', None),
        'pm25': data.get('pm25', None),
        'pm10': data.get('pm10', None)
    })

@app.route('/api/modbus/pir')
def get_pir_data():
    """PIR sensör verisi"""
    data = load_modbus_data()
    return jsonify({
        'motion': data.get('motion', None)
    })

@app.route('/api/modbus/mppt')
def get_mppt_data():
    """MPPT verisi"""
    data = load_modbus_data()
    return jsonify({
        'pv_voltage': data.get('pv_voltage', None),
        'pv_current': data.get('pv_current', None),
        'pv_power': data.get('pv_power', None)
    })

@app.route('/api/modbus/bms')
def get_bms_data():
    """BMS (Batarya) verisi"""
    data = load_modbus_data()
    return jsonify({
        'battery_voltage': data.get('battery_voltage', None),
        'battery_soc': data.get('battery_soc', None),
        'battery_temp': data.get('battery_temp', None)
    })

# ========================================
# API ENDPOINT'LERİ - KONTROL KOMUTLARI
# ========================================

COMMAND_FILE = 'modbus_commands.json'

def send_command(command_type, device, params):
    """
    modbus_reader.py'ye komut gönder
    Komut dosyaya yazılır, modbus_reader.py okur ve uygular
    """
    try:
        command = {
            'timestamp': datetime.now().isoformat(),
            'type': command_type,
            'device': device,
            'params': params,
            'status': 'pending'
        }
        
        # Mevcut komutları oku
        commands = []
        if os.path.exists(COMMAND_FILE):
            with open(COMMAND_FILE, 'r') as f:
                commands = json.load(f)
        
        # Yeni komutu ekle
        commands.append(command)
        
        # Dosyaya yaz
        with open(COMMAND_FILE, 'w') as f:
            json.dump(commands, f, indent=2)
        
        return True
    except Exception as e:
        print(f"⚠️ Komut gönderilemedi: {e}")
        return False

@app.route('/api/relay/<int:relay_id>/<int:state>')
def set_relay(relay_id, state):
    """
    Röle kontrolü
    relay_id: 1-4
    state: 0 (kapat) veya 1 (aç)
    """
    try:
        success = send_command(
            command_type='write_coil',
            device='relay',
            params={
                'relay_id': relay_id,
                'state': state
            }
        )
        
        if success:
            return jsonify({
                'success': True,
                'relay_id': relay_id,
                'state': 'ON' if state else 'OFF',
                'message': f'Röle {relay_id} komutu gönderildi'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Komut gönderilemedi'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/mppt/dimming/<int:value>')
def set_mppt_dimming(value):
    """
    MPPT Dimming kontrolü
    value: 0-100 (%)
    """
    try:
        if not (0 <= value <= 100):
            return jsonify({
                'success': False,
                'error': 'Değer 0-100 arasında olmalı'
            }), 400
        
        success = send_command(
            command_type='write_register',
            device='mppt',
            params={
                'register': 10,  # Dimming register adresi
                'value': value
            }
        )
        
        if success:
            return jsonify({
                'success': True,
                'dimming': value,
                'message': 'Dimming komutu gönderildi'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Komut gönderilemedi'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/mppt/rtc', methods=['POST'])
def set_mppt_rtc():
    """
    MPPT RTC saat ayarla
    POST JSON: {"date": "2025-10-23", "time": "16:30:00"}
    """
    try:
        data = request.get_json()
        date = data.get('date')
        time = data.get('time')
        
        if not date or not time:
            return jsonify({
                'success': False,
                'error': 'Tarih ve saat gerekli'
            }), 400
        
        success = send_command(
            command_type='write_rtc',
            device='mppt',
            params={
                'date': date,
                'time': time
            }
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'RTC ayar komutu gönderildi'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Komut gönderilemedi'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/serial/status')
def get_serial_status():
    """
    Serial port durumunu kontrol et
    modbus_reader.py'nin durumunu kontrol eder
    """
    try:
        data = load_modbus_data()
        last_update = data.get('last_update', None)
        
        if last_update:
            # Son güncelleme zamanını kontrol et
            last_time = datetime.fromisoformat(last_update)
            now = datetime.now()
            diff = (now - last_time).total_seconds()
            
            # 30 saniyeden eski ise offline
            if diff < 30:
                return jsonify({'online': True, 'last_update': last_update})
            else:
                return jsonify({'online': False, 'last_update': last_update})
        else:
            return jsonify({'online': False})
            
    except Exception as e:
        return jsonify({'online': False, 'error': str(e)})

# ========================================
# SİSTEM BİLGİLERİ
# ========================================

@app.route('/api/system/info')
def get_system_info():
    """Sistem bilgileri"""
    import platform
    
    try:
        return jsonify({
            'hostname': platform.node(),
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# HATA YÖNETİMİ
# ========================================

@app.errorhandler(404)
def not_found(e):
    """404 hatası"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    """500 hatası"""
    return jsonify({'error': 'Internal server error'}), 500

# ========================================
# UYGULAMA BAŞLATMA
# ========================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 nuGateway Flask Web Server")
    print("=" * 60)
    print("📡 Modbus Reader: modbus_reader.py (ayrı çalışmalı)")
    print("🌐 Web Interface: http://0.0.0.0:5000")
    print("=" * 60)
    
    # İlk veri yüklemesi
    load_modbus_data()
    
    # Flask'ı başlat
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000,
        threaded=True
    )