#!/bin/bash
#
# NuGateway MQTT Quick Install Script
# Bu script MQTT entegrasyonunu otomatik olarak kurar
#

echo "============================================================"
echo "🚀 NuGateway MQTT Kurulum"
echo "============================================================"

# Renk kodları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Mevcut dizini al
CURRENT_DIR="$(pwd)"
PROJECT_DIR="$CURRENT_DIR"
VENV_DIR="$CURRENT_DIR/nuEnv"

echo ""
echo "📁 Proje dizini: $PROJECT_DIR"
echo "🐍 Virtual environment: $VENV_DIR"
echo ""

# Virtual environment var mı kontrol et
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment bulunamadı${NC}"
    echo "🔧 Virtual environment oluşturuluyor..."
    python3 -m venv "$VENV_DIR"
fi

# Virtual environment'ı aktive et
echo "🔧 Virtual environment aktive ediliyor..."
source "$VENV_DIR/bin/activate"

# Gerekli paketleri kur
echo ""
echo "📦 Gerekli Python paketleri kuruluyor..."
pip install --upgrade pip
pip install paho-mqtt==1.6.1
pip install pyserial==3.5
pip install gpiozero==2.0.1
pip install Flask==2.3.3
pip install Flask-SocketIO==5.3.4
pip install Flask-Limiter==3.5.0

echo ""
echo -e "${GREEN}✅ Paketler kuruldu${NC}"

# Config dosyası yoksa örnek oluştur
if [ ! -f "$PROJECT_DIR/gateway_settings.json" ]; then
    echo ""
    echo "⚠️  gateway_settings.json bulunamadı, varsayılan oluşturuluyor..."
    cat > "$PROJECT_DIR/gateway_settings.json" << 'EOF'
{
  "gateway_name": "nuGateway",
  "serial_port": "/dev/ttyUSB0",
  "baudrate": 9600,
  "interval": 300,
  "data_bits": 8,
  "stop_bits": 1,
  "parity": "N",
  "location": "Kadikoy_Park_12",
  "mac_address": "",
  "ip_address": "",
  "enable_auth": false,
  "api_token": "",
  "mqtt_enabled": true,
  "mqtt_broker": "broker.nuteknoloji.com",
  "mqtt_port": 1883,
  "mqtt_topic": "nugateway/sensors",
  "mqtt_username": "",
  "mqtt_password": "",
  "log_level": "INFO",
  "log_file": "nugateway.log",
  "enable_data_logging": true,
  "data_log_file": "sensor_data.log",
  "alarm_enabled": true,
  "temp_alarm_high": 35.0,
  "temp_alarm_low": 5.0,
  "humidity_alarm_high": 85.0,
  "co2_alarm_high": 2000.0,
  "battery_soc_alarm_low": 20,
  "use_simulator": false,
  "modbus_in_flask": false
}
EOF
    echo -e "${GREEN}✅ gateway_settings.json oluşturuldu${NC}"
else
    echo -e "${GREEN}✅ gateway_settings.json zaten var${NC}"
fi

# Kullanıcıyı gpio ve dialout grubuna ekle
echo ""
echo "🔧 Kullanıcı izinleri ayarlanıyor..."
sudo usermod -a -G gpio $USER 2>/dev/null || echo "gpio grubu bulunamadı (normal)"
sudo usermod -a -G dialout $USER

# Systemd service kurulumu (opsiyonel)
echo ""
read -p "Systemd service kurulsun mu? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Service dosyası oluştur
    SERVICE_FILE="/tmp/nugateway-mqtt.service"
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=NuGateway MQTT Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python3 $PROJECT_DIR/nugateway_mqtt.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    sudo cp "$SERVICE_FILE" /etc/systemd/system/nugateway-mqtt.service
    sudo systemctl daemon-reload
    sudo systemctl enable nugateway-mqtt.service
    
    echo -e "${GREEN}✅ Systemd service kuruldu${NC}"
    echo ""
    echo "Service komutları:"
    echo "  Başlat:        sudo systemctl start nugateway-mqtt.service"
    echo "  Durdur:        sudo systemctl stop nugateway-mqtt.service"
    echo "  Durum:         sudo systemctl status nugateway-mqtt.service"
    echo "  Loglar:        sudo journalctl -u nugateway-mqtt.service -f"
    
    rm "$SERVICE_FILE"
fi

echo ""
echo "============================================================"
echo -e "${GREEN}✅ Kurulum tamamlandı!${NC}"
echo "============================================================"
echo ""
echo "📝 Sonraki adımlar:"
echo ""
echo "1. Config dosyasını düzenleyin:"
echo "   nano $PROJECT_DIR/gateway_settings.json"
echo ""
echo "2. Serial port'u kontrol edin:"
echo "   ls -la /dev/ttyUSB*"
echo ""
echo "3. Test edin:"
echo "   cd $PROJECT_DIR"
echo "   source $VENV_DIR/bin/activate"
echo "   python3 nugateway_mqtt.py"
echo ""
echo "4. Veya service olarak başlatın:"
echo "   sudo systemctl start nugateway-mqtt.service"
echo "   sudo journalctl -u nugateway-mqtt.service -f"
echo ""
echo -e "${YELLOW}⚠️  DİKKAT: İzin değişiklikleri için çıkış yapıp tekrar giriş yapın!${NC}"
echo "============================================================"
