#!/usr/bin/env python3
"""
NuBank Complete Service - Full BMS Support
- Waveshare 3 kanal röle kontrolü
- Ekran dikey döndürme (270°)
- Video loop oynatma
- TAM Modbus veri toplama (BMS tüm hücreler, MPPT, ENV, LDR, PIR)
- MQTT publish (broker.nuteknoloji.com)
- 2 saat otomatik kapanma
"""

import subprocess
import time
import signal
import sys
import os
import json
import logging
import threading
from datetime import datetime, timedelta
import RPi.GPIO as GPIO

# Modbus ve MQTT için import
import serial
import struct
from typing import Optional, Dict, List
import paho.mqtt.client as mqtt

# ==================== AYARLAR ====================

# Video
VIDEO_PATH = "/home/cafer/Desktop/NuGateway/videos/NuReklam.mp4"

# Röle Pinleri (Waveshare 3Ch)
RELAY_PINS = {"CH1": 26, "CH2": 20, "CH3": 21}

# Modbus
MODBUS_PORT = '/dev/ttyUSB0'
MODBUS_BAUDRATE = 9600

# MQTT
MQTT_BROKER = "broker.nuteknoloji.com"
MQTT_PORT = 1883
MQTT_USERNAME = ""  # Gerekirse doldur
MQTT_PASSWORD = ""  # Gerekirse doldur
DEVICE_ID = "KARADAG-BANK-01"
LOCATION = "Podgorica-Karadag"
DEVICE_TYPE = 0xC1  # Akıllı Banklar için sabit

# Zamanlama
AUTO_OFF_HOURS = 2  # 2 saat sonra kapat
MODBUS_READ_INTERVAL = 300  # 5 dakikada bir veri oku (300 saniye)

# ==================== LOGGING ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/cafer/Desktop/NuGateway/nubank.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== MODBUS READER ====================

class ModbusReader:
    """Modbus RTU reader with full BMS support"""
    
    def __init__(self, port: str, baudrate: int):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        
    def connect(self) -> bool:
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            logger.info(f"✅ Modbus connected: {self.port}")
            return True
        except Exception as e:
            logger.error(f"❌ Modbus connection failed: {e}")
            return False
    
    def disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
    
    @staticmethod
    def calculate_crc(data: List[int]) -> List[int]:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return [crc & 0xFF, (crc >> 8) & 0xFF]
    
    def read_registers(self, slave_id: int, start_address: int, 
                       count: int, function_code: int = 0x04) -> Optional[List[int]]:
        if not self.serial or not self.serial.is_open:
            return None
        
        request = [
            slave_id, function_code,
            (start_address >> 8) & 0xFF, start_address & 0xFF,
            (count >> 8) & 0xFF, count & 0xFF
        ]
        crc = self.calculate_crc(request)
        request.extend(crc)
        
        try:
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.serial.write(bytes(request))
            time.sleep(0.1)
            
            expected_length = 3 + (count * 2) + 2
            response = list(self.serial.read(expected_length))
            
            if not response or len(response) < 5:
                return None
            
            byte_count = response[2]
            data_bytes = response[3:3+byte_count]
            
            registers = []
            for i in range(0, len(data_bytes), 2):
                if i + 1 < len(data_bytes):
                    reg_value = (data_bytes[i] << 8) | data_bytes[i+1]
                    registers.append(reg_value)
            
            return registers
        except:
            return None
    
    def read_bms_full(self) -> Dict:
        """Full BMS okuma - tüm hücreler ve detaylar"""
        
        def bms_send(cmd, rw=0x01, data=b""):
            """BMS özel protokol"""
            frame = bytes([0x3D, 0x01, 0x02, cmd, rw, 0x00, len(data)]) + data
            chk = (sum(frame) & 0xFF)
            tx = frame + bytes([chk])
            
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.serial.write(tx)
            
            time.sleep(0.8)
            rx = self.serial.read(self.serial.in_waiting or 255)
            
            # Read in chunks
            for _ in range(3):
                time.sleep(0.2)
                extra = self.serial.read(self.serial.in_waiting or 255)
                if extra:
                    rx += extra
                else:
                    break
            
            if not rx:
                return None
            
            # Verify checksum
            if (sum(rx[:-1]) & 0xFF) != rx[-1]:
                return None
            
            return rx
        
        def u16_le(buf, i):
            """Unsigned 16-bit little-endian"""
            return buf[i] | (buf[i + 1] << 8)
        
        def i16_le(buf, i):
            """Signed 16-bit little-endian"""
            v = u16_le(buf, i)
            return v - 65536 if v > 32767 else v
        
        bms_data = {}
        
        try:
            # 1. Cell count
            rx = bms_send(0x27)
            series_count = 4  # Default
            if rx and len(rx) > 6:
                d = rx[6:-1]
                series_count = d[-1] if 1 <= d[-1] <= 24 else 4
            
            time.sleep(0.5)
            
            # 2. Real-time data
            rx = bms_send(0x00)
            if rx and len(rx) > 20:
                d = rx[6:-1][1:]  # Skip first byte
                
                # Cell voltages
                cells = [round(u16_le(d, i * 2) / 1000.0, 3) for i in range(series_count)]
                bms_data['bms_cell_1_voltage'] = cells[0] if len(cells) > 0 else 0.0
                bms_data['bms_cell_2_voltage'] = cells[1] if len(cells) > 1 else 0.0
                bms_data['bms_cell_3_voltage'] = cells[2] if len(cells) > 2 else 0.0
                bms_data['bms_cell_4_voltage'] = cells[3] if len(cells) > 3 else 0.0
                
                # Find pack voltage/current position
                total_v = sum(cells)
                v_guess = int(round(total_v * 100))
                v_low, v_high = v_guess - 12, v_guess + 12
                
                # Skip zero padding
                start = max(2 * series_count, 8)
                zero_run = 0
                base_start = start
                for i in range(start, len(d)):
                    if d[i] == 0x00:
                        zero_run += 1
                    else:
                        if zero_run >= 16:
                            base_start = i
                            break
                        zero_run = 0
                
                # Find pack voltage marker
                pack_idx = None
                for i in range(base_start, len(d) - 8):
                    val = u16_le(d, i)
                    if v_low <= val <= v_high:
                        pack_idx = i
                        break
                
                if pack_idx is None:
                    vpack = round(total_v, 2)
                    ipack = 0.0
                    soc = 0
                    soh = 0
                else:
                    vpack = round(u16_le(d, pack_idx) / 100.0, 2)
                    ipack = round(i16_le(d, pack_idx + 2) / 100.0, 2)
                    
                    cand_soc = d[pack_idx + 6] if (pack_idx + 6) < len(d) else 255
                    cand_soh = d[pack_idx + 7] if (pack_idx + 7) < len(d) else 255
                    soc = cand_soc if 0 <= cand_soc <= 100 else 0
                    soh = cand_soh if 0 <= cand_soh <= 100 else 0
                
                bms_data['bms_battery_voltage'] = vpack
                bms_data['bms_battery_current'] = ipack
                bms_data['bms_battery_soc'] = soc
                bms_data['bms_battery_soh'] = soh
                bms_data['bms_battery_power'] = round(vpack * ipack, 2)
            
            time.sleep(0.5)
            
            # 3. MOS status
            for cmd, key in [(0x2D, "bms_discharge_mos_status"), 
                            (0x2E, "bms_charge_mos_status")]:
                rx = bms_send(cmd)
                if rx and len(rx) >= 8:
                    state = "ON" if rx[7] == 1 else "OFF"
                    bms_data[key] = state
                else:
                    bms_data[key] = "UNKNOWN"
                time.sleep(0.5)
            
            logger.info(f"   ✓ BMS: {bms_data.get('bms_battery_voltage')}V, {bms_data.get('bms_battery_soc')}%")
            logger.info(f"   ✓ Cells: {bms_data.get('bms_cell_1_voltage')}V, {bms_data.get('bms_cell_2_voltage')}V, {bms_data.get('bms_cell_3_voltage')}V, {bms_data.get('bms_cell_4_voltage')}V")
            
        except Exception as e:
            logger.error(f"BMS read error: {e}")
        
        return bms_data
    
    def read_mppt(self) -> Dict:
        """MPPT okuma (Slave 0x01)"""
        data = {}
        
        pv_v = self.read_registers(0x01, 0x304E, 1, 0x04)
        if pv_v: 
            data['mppt_pv_voltage'] = round(pv_v[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        pv_i = self.read_registers(0x01, 0x304F, 1, 0x04)
        if pv_i: 
            data['mppt_pv_current'] = round(pv_i[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        bat_soc = self.read_registers(0x01, 0x3045, 1, 0x04)
        if bat_soc:
            data['mppt_battery_soc'] = bat_soc[0]
        
        time.sleep(0.05)
        
        bat_v = self.read_registers(0x01, 0x3046, 1, 0x04)
        if bat_v: 
            data['mppt_battery_voltage'] = round(bat_v[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        bat_i = self.read_registers(0x01, 0x3047, 1, 0x04)
        if bat_i:
            raw = bat_i[0]
            if raw > 0x7FFF:
                raw = raw - 0x10000
            data['mppt_battery_current'] = round(raw / 100.0, 2)
        
        # Calculate powers
        if 'mppt_pv_voltage' in data and 'mppt_pv_current' in data:
            data['mppt_pv_power'] = round(data['mppt_pv_voltage'] * data['mppt_pv_current'], 2)
        
        if 'mppt_battery_voltage' in data and 'mppt_battery_current' in data:
            data['mppt_battery_power'] = round(data['mppt_battery_voltage'] * data['mppt_battery_current'], 2)
        
        if data:
            logger.info(f"   ✓ MPPT PV: {data.get('mppt_pv_voltage')}V, {data.get('mppt_pv_current')}A")
        
        return data
    
    def read_env(self) -> Dict:
        """ENV sensor (Slave 0x7B)"""
        data = {}
        try:
            # CO2
            co2 = self.read_registers(0x7B, 0x0008, 2, 0x03)
            if co2 and len(co2) >= 2:
                co2_bytes = struct.pack('>HH', co2[0], co2[1])
                data['env_co2'] = round(struct.unpack('>f', co2_bytes)[0], 1)
            
            time.sleep(0.05)
            
            # Temperature
            temp = self.read_registers(0x7B, 0x000E, 2, 0x03)
            if temp and len(temp) >= 2:
                temp_bytes = struct.pack('>HH', temp[0], temp[1])
                data['env_temperature'] = round(struct.unpack('>f', temp_bytes)[0], 1)
            
            time.sleep(0.05)
            
            # Humidity
            hum = self.read_registers(0x7B, 0x0010, 2, 0x03)
            if hum and len(hum) >= 2:
                hum_bytes = struct.pack('>HH', hum[0], hum[1])
                data['env_humidity'] = round(struct.unpack('>f', hum_bytes)[0], 1)
            
            if data:
                logger.info(f"   ✓ ENV: {data.get('env_temperature')}°C, {data.get('env_humidity')}%, CO2: {data.get('env_co2')}ppm")
        except:
            pass
        return data
    
    def read_ldr(self) -> Dict:
        """LDR sensor (Slave 0x04)"""
        data = {}
        ldr = self.read_registers(0x04, 0x0000, 2, 0x03)
        if ldr and len(ldr) >= 2:
            ldr_value = (ldr[0] << 16) | ldr[1]
            data['ldr_lux'] = ldr_value
            logger.info(f"   ✓ LDR: {ldr_value} lux")
        return data
    
    def read_pir(self) -> Dict:
        """PIR sensor (Slave 0x02)"""
        data = {}
        pir = self.read_registers(0x02, 0x0000, 1, 0x03)
        if pir:
            data['pir_motion_detected'] = bool(pir[0])
            logger.info(f"   ✓ PIR: {'Motion' if pir[0] else 'No motion'}")
        return data
    
    def read_all(self) -> Dict:
        """Tüm cihazları oku - FULL detay"""
        all_data = {}
        
        logger.info("📊 Modbus tam okuma başlıyor...")
        
        # MPPT
        mppt = self.read_mppt()
        if mppt:
            all_data.update(mppt)
        time.sleep(0.3)
        
        # ENV
        env = self.read_env()
        if env:
            all_data.update(env)
        time.sleep(0.3)
        
        # LDR
        ldr = self.read_ldr()
        if ldr:
            all_data.update(ldr)
        time.sleep(0.3)
        
        # BMS - TAM DETAY
        bms = self.read_bms_full()
        if bms:
            all_data.update(bms)
        time.sleep(0.3)
        
        # PIR
        pir = self.read_pir()
        if pir:
            all_data.update(pir)
        
        # Metadata ekle
        all_data['timestamp'] = datetime.now().isoformat()
        all_data['device_id'] = DEVICE_ID
        all_data['location'] = LOCATION
        all_data['device_type'] = DEVICE_TYPE
        
        return all_data


# ==================== MQTT CLIENT ====================

class MQTTPublisher:
    """MQTT yayıncı"""
    
    def __init__(self, broker: str, port: int, device_id: str):
        self.broker = broker
        self.port = port
        self.device_id = device_id
        self.client = mqtt.Client(client_id=device_id)
        self.connected = False
        
        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
        self.topic = f"nugateway/{device_id}/telemetry"
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"✅ MQTT connected: {self.broker}")
        else:
            logger.error(f"❌ MQTT connection failed: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.warning("⚠️  MQTT disconnected")
    
    def connect(self) -> bool:
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            time.sleep(2)
            return self.connected
        except Exception as e:
            logger.error(f"❌ MQTT connect error: {e}")
            return False
    
    def publish(self, data: Dict) -> bool:
        if not self.connected:
            logger.warning("⚠️  MQTT not connected, skipping publish")
            return False
        
        try:
            payload = json.dumps(data, indent=2)
            result = self.client.publish(self.topic, payload, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"✅ MQTT published: {len(data)} parameters")
                return True
            else:
                logger.error(f"❌ MQTT publish failed: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"❌ MQTT publish error: {e}")
            return False
    
    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()


# ==================== MAIN SERVICE ====================

class NuBankService:
    """Komple NuBank servisi"""
    
    def __init__(self):
        self.running = True
        self.player_process = None
        self.start_time = datetime.now()
        self.auto_off_time = self.start_time + timedelta(hours=AUTO_OFF_HOURS)
        
        # GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in RELAY_PINS.values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)  # KAPALI
        
        # Modbus
        self.modbus = ModbusReader(MODBUS_PORT, MODBUS_BAUDRATE)
        
        # MQTT
        self.mqtt = MQTTPublisher(MQTT_BROKER, MQTT_PORT, DEVICE_ID)
        
        # Signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info("=" * 70)
        logger.info("🚀 NuBank Complete Service - FULL BMS")
        logger.info("=" * 70)
    
    def _signal_handler(self, sig, frame):
        logger.info("⚠️  Kapatma sinyali alındı...")
        self.running = False
    
    def relays_on(self):
        logger.info("🔌 Röleler açılıyor (CH1, CH2, CH3)...")
        for name, pin in RELAY_PINS.items():
            GPIO.output(pin, GPIO.LOW)  # LOW = AÇIK
            logger.info(f"   ✅ {name} (GPIO {pin}): AÇIK")
    
    def relays_off(self):
        logger.info("🔌 Röleler kapatılıyor...")
        for name, pin in RELAY_PINS.items():
            GPIO.output(pin, GPIO.HIGH)  # HIGH = KAPALI
            logger.info(f"   ⭕ {name} (GPIO {pin}): KAPALI")
    
    def rotate_screen(self):
        logger.info("🖥️  Ekran dikey yapılıyor (270°)...")
        try:
            subprocess.run(
                ["wlr-randr", "--output", "HDMI-A-1", "--transform", "90"],
                timeout=10, check=False, capture_output=True,
                env={**os.environ, "WAYLAND_DISPLAY": "wayland-1", "XDG_RUNTIME_DIR": "/run/user/1000"}
            )
            logger.info("   ✅ Ekran döndürüldü")
        except Exception as e:
            logger.error(f"   ❌ Ekran hatası: {e}")
    
    def start_video(self):
        if self.player_process and self.player_process.poll() is None:
            return
        
        logger.info("🎬 Video başlatılıyor...")
        try:
            self.player_process = subprocess.Popen(
                ["mpv", "--fullscreen", "--loop-file=inf", "--no-terminal", 
                 "--no-osc", "--no-input-default-bindings", VIDEO_PATH],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env={**os.environ, "DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-1", 
                     "XDG_RUNTIME_DIR": "/run/user/1000"}
            )
            logger.info(f"   ✅ Video loop (PID: {self.player_process.pid})")
        except Exception as e:
            logger.error(f"   ❌ Video hatası: {e}")
    
    def stop_video(self):
        if self.player_process:
            try:
                self.player_process.terminate()
                self.player_process.wait(timeout=5)
            except:
                self.player_process.kill()
            self.player_process = None
    
    def modbus_mqtt_loop(self):
        """Arka planda Modbus okuma ve MQTT gönderme"""
        last_read = 0
        
        while self.running:
            if time.time() - last_read >= MODBUS_READ_INTERVAL:
                try:
                    # Modbus oku - TAM DETAY
                    data = self.modbus.read_all()
                    
                    # MQTT publish
                    self.mqtt.publish(data)
                    
                    # Local kaydet
                    with open('/home/cafer/Desktop/NuGateway/telemetry.json', 'w') as f:
                        json.dump(data, f, indent=2)
                    
                    last_read = time.time()
                except Exception as e:
                    logger.error(f"Modbus/MQTT hatası: {e}")
            
            time.sleep(10)
    
    def run(self):
        logger.info(f"📍 Location: {LOCATION}")
        logger.info(f"🆔 Device ID: {DEVICE_ID}")
        logger.info(f"🔧 Device Type: 0x{DEVICE_TYPE:02X}")
        logger.info(f"⏰ Başlangıç: {self.start_time.strftime('%H:%M:%S')}")
        logger.info(f"⏰ Kapanma: {self.auto_off_time.strftime('%H:%M:%S')}")
        logger.info(f"📡 MQTT: {MQTT_BROKER} → {DEVICE_ID}/telemetry")
        logger.info("=" * 70)
        
        # 1. Modbus bağlan
        if not self.modbus.connect():
            logger.warning("⚠️  Modbus bağlanamadı, devam ediliyor...")
        
        # 2. MQTT bağlan
        if not self.mqtt.connect():
            logger.warning("⚠️  MQTT bağlanamadı, devam ediliyor...")
        
        # 3. Röleleri aç
        self.relays_on()
        time.sleep(3)
        
        # 4. Ekranı döndür
        self.rotate_screen()
        time.sleep(2)
        
        # 5. Videoyu başlat
        self.start_video()
        
        # 6. Modbus/MQTT thread başlat
        modbus_thread = threading.Thread(target=self.modbus_mqtt_loop, daemon=True)
        modbus_thread.start()
        
        # 7. Ana döngü
        logger.info("💚 Sistem aktif - Video + Telemetry (Full BMS) çalışıyor...")
        last_log = time.time()
        
        while self.running:
            # Video kontrolü
            if self.player_process and self.player_process.poll() is not None:
                logger.warning("⚠️  Video durmuş, yeniden başlatılıyor...")
                self.start_video()
            
            # Zaman kontrolü
            now = datetime.now()
            if now >= self.auto_off_time:
                logger.info("⏰ 2 SAAT DOLDU! Kapatılıyor...")
                break
            
            # Durum logu (her 10 dakika)
            if time.time() - last_log >= 600:
                remaining = int((self.auto_off_time - now).total_seconds() / 60)
                logger.info(f"💚 Aktif | Kalan: {remaining} dakika | Full BMS telemetry")
                last_log = time.time()
            
            time.sleep(5)
        
        self.shutdown()
    
    def shutdown(self):
        logger.info("=" * 70)
        logger.info("🔄 Kapatılıyor...")
        logger.info("=" * 70)
        
        self.stop_video()
        time.sleep(1)
        self.relays_off()
        
        self.modbus.disconnect()
        self.mqtt.disconnect()
        
        GPIO.cleanup()
        logger.info("✅ Temizlendi")
        logger.info("👋 NuBank Service kapatıldı")


if __name__ == "__main__":
    try:
        service = NuBankService()
        service.run()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Ctrl+C ile durduruldu")
    except Exception as e:
        logger.error(f"❌ Hata: {e}", exc_info=True)
    finally:
        try:
            GPIO.setmode(GPIO.BCM)
            for pin in [26, 20, 21]:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)
            GPIO.cleanup()
        except:
            pass
