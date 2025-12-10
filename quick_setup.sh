#!/bin/bash
#
# NuGateway MQTT Hızlı Kurulum (Tek Komut)
# Kullanım: ./quick_setup.sh
#

echo "============================================================"
echo "⚡ NuGateway MQTT Hızlı Kurulum"
echo "============================================================"

# Renk kodları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Mevcut dizin
CURRENT_DIR="$(pwd)"
VENV_DIR="$CURRENT_DIR/nuEnv"

echo ""
echo "📁 Dizin: $CURRENT_DIR"
echo ""

# 1. Virtual environment kontrol
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ nuEnv bulunamadı!"
    exit 1
fi

# 2. Activate
echo "🔧 Virtual environment aktive ediliyor..."
source "$VENV_DIR/bin/activate"

# 3. MQTT paketi kur
echo "📦 paho-mqtt kuruluyor..."
pip install paho-mqtt==1.6.1 -q

# 4. Test dosyalarını kontrol et
echo ""
echo "📋 Dosya kontrolü..."
for file in mqtt_client.py nugateway_mqtt.py modbus_reader.py config.py logger.py relay_control.py; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✅${NC} $file"
    else
        echo -e "  ${RED}❌${NC} $file - BULUNAMADI!"
    fi
done

# 5. Import test
echo ""
echo "🧪 Import testi yapılıyor..."
python3 << 'EOF'
try:
    from modbus_reader import ModbusReader
    print("✅ ModbusReader import başarılı")
except Exception as e:
    print(f"❌ ModbusReader import hatası: {e}")

try:
    from mqtt_client import MQTTClient
    print("✅ MQTTClient import başarılı")
except Exception as e:
    print(f"❌ MQTTClient import hatası: {e}")

try:
    from relay_control import relay_controller
    print("✅ relay_controller import başarılı")
except Exception as e:
    print(f"❌ relay_controller import hatası: {e}")
EOF

echo ""
echo "============================================================"
echo -e "${GREEN}✅ Kurulum kontrolü tamamlandı!${NC}"
echo "============================================================"
echo ""
echo "🚀 Şimdi çalıştırabilirsiniz:"
echo ""
echo "   python3 nugateway_mqtt.py"
echo ""
echo "============================================================"
