"""
Nu Gateway - Modbus Reader (RAW Serial)
Doğrudan serial port kullanarak Modbus haberleşmesi
Excel'den alınan register bilgilerine göre özelleştirilmiş
"""

import serial
import time
import json
import struct
from datetime import datetime

# ========================================
# KONFIGÜRASYON
# ========================================

SERIAL_PORT = '/dev/ttyUSB0'
BAUDRATE = 9600
TIMEOUT = 0.5
READ_INTERVAL = 5  # Okuma periyodu (saniye)

MODBUS_DATA_FILE = 'modbus_data.json'
COMMAND_FILE = 'modbus_commands.json'

# Slave ID'ler
SLAVE_BMS = 0x3D      # 61 (BMS)
SLAVE_MPPT = 0x01     # 10 (Lumiax MPPT)
SLAVE_ENV = 0x7B      # 123 (Çevre sensörü)
SLAVE_LDR = 0x04      # 4 (LDR)

# Global değişkenler
ser = None
modbus_data = {}

# ========================================
# CRC-16 MODBUS HESAPLAMA
# ========================================

def calculate_crc16(data):
    """Modbus CRC-16 hesapla (LSB first)"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def add_crc(frame):
    """Frame'e CRC ekle"""
    crc = calculate_crc16(frame)
    return frame + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

def check_crc(frame):
    """CRC'yi kontrol et"""
    if len(frame) < 3:
        return False
    data = frame[:-2]
    received_crc = frame[-2] | (frame[-1] << 8)
    calculated_crc = calculate_crc16(data)
    return received_crc == calculated_crc

# ========================================
# SERIAL PORT İŞLEMLERİ
# ========================================

def open_serial():
    """Serial portu aç"""
    global ser
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=TIMEOUT
        )
        print(f"✅ Serial port açıldı: {SERIAL_PORT} @ {BAUDRATE} baud")
        time.sleep(0.1)  # Port stabilize olsun
        return True
    except Exception as e:
        print(f"❌ Serial port açılamadı: {e}")
        return False

def close_serial():
    """Serial portu kapat"""
    global ser
    if ser and ser.is_open:
        ser.close()
        print("🔒 Serial port kapatıldı")

def send_receive(tx_frame, expected_length=None, timeout=0.5):
    """Modbus frame gönder ve cevap al"""
    try:
        if not ser or not ser.is_open:
            return None
        
        # Buffer'ı temizle
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Frame gönder
        ser.write(tx_frame)
        print(f"    TX: {tx_frame.hex().upper()}")
        
        # Cevap bekle
        time.sleep(0.05)  # Cihazın cevap vermesi için kısa bekleme
        
        if expected_length:
            # Belirli uzunlukta cevap bekle
            rx_data = ser.read(expected_length)
        else:
            # Mevcut buffer'daki tüm veriyi oku
            rx_data = ser.read(ser.in_waiting or 255)
        
        if len(rx_data) > 0:
            print(f"    RX: {rx_data.hex().upper()}")
            return rx_data
        else:
            print(f"    RX: TIMEOUT")
            return None
            
    except Exception as e:
        print(f"    ⚠️ Send/Receive hatası: {e}")
        return None

# ========================================
# BMS OKUMA (Slave 0x3D)
# ========================================

def read_bms():
    """BMS verilerini oku ve parametreleri anlamlı biçimde çöz"""
    print("  📦 BMS okuma...")

    def bms_send(cmd, rw=0x01, data=b""):
        frame = bytes([0x3D, 0x01, 0x02, cmd, rw, 0x00, len(data)]) + data
        chk = (sum(frame) & 0xFF)
        tx = frame + bytes([chk])
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(tx)
        print(f"    TX: {tx.hex().upper()}")
        time.sleep(0.8)
        rx = ser.read(ser.in_waiting or 255)
        for _ in range(3):
            time.sleep(0.2)
            extra = ser.read(ser.in_waiting or 255)
            if extra:
                rx += extra
            else:
                break
        if not rx:
            print(f"    ⚠️ RX: TIMEOUT (Cmd=0x{cmd:02X})")
            return None
        print(f"    RX: {rx.hex().upper()}")
        if (sum(rx[:-1]) & 0xFF) != rx[-1]:
            print(f"    ⚠️ Checksum hatası (Cmd=0x{cmd:02X})")
            return None
        return rx

    def u16_le(buf, i):
        return buf[i] | (buf[i + 1] << 8)

    def i16_le(buf, i):
        v = u16_le(buf, i)
        return v - 65536 if v > 32767 else v

    try:
        # -------- 0x27: Hücre sayısı --------
        rx = bms_send(0x27)
        series_count = None
        if rx and len(rx) > 6:
            d = rx[6:-1]
            series_count = d[-1] if 1 <= d[-1] <= 24 else 4
            print(f"    ✅ Cevap alındı (Hücre Sayısı: {series_count})")
        else:
            print("    ⚠️ Cevap yok (Cmd=0x27)")
            print("    ⚠️ Hücre sayısı okunamadı, varsayılan 4 olarak alındı.")
            series_count = 4
        time.sleep(0.5)

        # -------- 0x00: Gerçek zamanlı veri (dinamik pack konumu) --------
        rx = bms_send(0x00)
        if rx and len(rx) > 20:
            # Protokolde payload: rx[6:-1], milat kodunda +1 offset kullanılıyor
            d = rx[6:-1][1:]

            # 1) Hücre voltajları
            cells = [round(u16_le(d, i * 2) / 1000.0, 3) for i in range(series_count)]
            for i, v in enumerate(cells, 1):
                print(f"    ✅ Cevap alındı (Cell {i}: {v:.3f}V)")

            # 2) Pack V/I için dinamik konum:
            #    - uzun 0x00 dolgusu biter; ardından anlamlı blok başlar
            #    - pack voltajı, hücre toplamına (×100) yakın u16_le değerdir
            total_v = sum(cells)
            v_guess = int(round(total_v * 100))           # 13.36V -> 1336
            v_low, v_high = v_guess - 12, v_guess + 12    # ±12 tolerans

            # "0x00 dolgu"yu atla (>=16 adet ardışık 0x00)
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

            # Hücre toplamına yakın değeri tara
            pack_idx = None
            for i in range(base_start, len(d) - 8):
                val = u16_le(d, i)
                if v_low <= val <= v_high:
                    pack_idx = i
                    break

            if pack_idx is None:
                # bulunamazsa hücre toplamına düş
                vpack = round(total_v, 2)
                ipack = 0.0
                soc = 0
                soh = 0
                print(f"    ⚠️ Pack marker bulunamadı, toplamdan tahmin: {vpack:.2f}V")
            else:
                # 3) Pack & Current
                vpack = round(u16_le(d, pack_idx) / 100.0, 2)
                ipack = round(i16_le(d, pack_idx + 2) / 100.0, 2)

                # 4) SOC / SOH — pack sonrası +6 / +7 tek bayt
                cand_soc = d[pack_idx + 6] if (pack_idx + 6) < len(d) else 255
                cand_soh = d[pack_idx + 7] if (pack_idx + 7) < len(d) else 255
                soc = cand_soc if 0 <= cand_soc <= 100 else 0
                soh = cand_soh if 0 <= cand_soh <= 100 else 0

            print(f"    ✅ Cevap alındı (Pack Voltage: {vpack:.2f}V, Current: {ipack:.2f}A, SOC: {soc}%, SOH: {soh}%)")
            modbus_data.update({
                "bms_cells": cells,
                "bms_voltage": vpack,
                "bms_current": ipack,
                "bms_soc": soc,
                "bms_soh": soh
            })
        else:
            print("    ⚠️ Cevap yok (Cmd=0x00)")
        time.sleep(0.5)

        # -------- 0x01: Limit/koruma parametreleri --------
        rx = bms_send(0x01)
        if rx and len(rx) >= 6 + 56 + 1:  # başlık (6) + payload (56) + checksum (1)
            d = rx[6:6 + 56]  # 56 byte payload

            # Hücre voltaj korumaları (mV) ve gecikmeler (ms)
            cell_ovp_mv         = u16_le(d, 0)    # 3650 mV
            cell_ovp_rel_mv     = u16_le(d, 2)    # 3500 mV
            ovp_delay_ms        = u16_le(d, 4)    # 1000 ms
            cell_uvp_mv         = u16_le(d, 6)    # 2700 mV
            cell_uvp_rel_mv     = u16_le(d, 8)    # 2900 mV
            uvp_delay_ms        = u16_le(d, 10)   # 1000 ms

            # Sıcaklık eşikleri (°C)
            t_hot_1_c           = u16_le(d, 12)   # 75 °C
            t_hot_2_c           = u16_le(d, 14)   # 65 °C
            t_hot_3_c           = u16_le(d, 16)   # 55 °C
            t_hot_4_c           = u16_le(d, 18)   # 45 °C
            t_limit_1           = u16_le(d, 20)   # 100
            t_limit_2           = u16_le(d, 22)   # 80

            # Negatif sıcaklıklar (işaretli, °C)
            t_cold_1_c          = i16_le(d, 24)   # -40 °C
            t_cold_2_c          = i16_le(d, 26)   # -30 °C
            t_cold_3_c          = i16_le(d, 28)   # -20 °C

            # Gecikme/ham değerler
            delay_1             = u16_le(d, 30)   # 5
            delay_2             = u16_le(d, 32)   # 30
            delay_3_ms          = u16_le(d, 34)   # 1000 ms
            delay_4             = u16_le(d, 36)   # 30
            delay_5_ms          = u16_le(d, 38)   # 1000 ms

            # Kalan ham eşik/nokta değerleri
            raw_x1              = u16_le(d, 40)   # 70
            raw_x2              = u16_le(d, 42)   # 1000
            raw_x3              = u16_le(d, 44)   # 140
            raw_x4              = u16_le(d, 46)   # 100
            raw_x5              = u16_le(d, 48)   # 200
            raw_x6              = u16_le(d, 50)   # 300
            raw_x7              = u16_le(d, 52)   # 975
            raw_x8              = u16_le(d, 54)   # 0

            # Konsola detaylı döküm
            print("    ✅ Cevap alındı (Koruma/Limit parametreleri)")
            print(f"       OVP: {cell_ovp_mv} mV (release: {cell_ovp_rel_mv} mV, delay: {ovp_delay_ms} ms)")
            print(f"       UVP: {cell_uvp_mv} mV (release: {cell_uvp_rel_mv} mV, delay: {uvp_delay_ms} ms)")
            print(f"       Temp hot thresholds: {t_hot_1_c} / {t_hot_2_c} / {t_hot_3_c} / {t_hot_4_c} °C")
            print(f"       Temp limits: {t_limit_1} / {t_limit_2}")
            print(f"       Temp cold thresholds: {t_cold_1_c} / {t_cold_2_c} / {t_cold_3_c} °C")
            print(f"       Delays: {delay_1}, {delay_2}, {delay_3_ms} ms, {delay_4}, {delay_5_ms} ms")
            print(f"       Raw X: {raw_x1}, {raw_x2}, {raw_x3}, {raw_x4}, {raw_x5}, {raw_x6}, {raw_x7}, {raw_x8}")

            # JSON'a yaz
            modbus_data.update({
                "bms_cell_ovp_mv": cell_ovp_mv,
                "bms_cell_ovp_release_mv": cell_ovp_rel_mv,
                "bms_ovp_delay_ms": ovp_delay_ms,
                "bms_cell_uvp_mv": cell_uvp_mv,
                "bms_cell_uvp_release_mv": cell_uvp_rel_mv,
                "bms_uvp_delay_ms": uvp_delay_ms,

                "bms_t_hot_1_c": t_hot_1_c,
                "bms_t_hot_2_c": t_hot_2_c,
                "bms_t_hot_3_c": t_hot_3_c,
                "bms_t_hot_4_c": t_hot_4_c,
                "bms_t_limit_1": t_limit_1,
                "bms_t_limit_2": t_limit_2,

                "bms_t_cold_1_c": t_cold_1_c,
                "bms_t_cold_2_c": t_cold_2_c,
                "bms_t_cold_3_c": t_cold_3_c,

                "bms_delay_1": delay_1,
                "bms_delay_2": delay_2,
                "bms_delay_3_ms": delay_3_ms,
                "bms_delay_4": delay_4,
                "bms_delay_5_ms": delay_5_ms,

                "bms_raw_x1": raw_x1,
                "bms_raw_x2": raw_x2,
                "bms_raw_x3": raw_x3,
                "bms_raw_x4": raw_x4,
                "bms_raw_x5": raw_x5,
                "bms_raw_x6": raw_x6,
                "bms_raw_x7": raw_x7,
                "bms_raw_x8": raw_x8
            })
        else:
            print("    ⚠️ Cevap yok (Cmd=0x01)")
        time.sleep(0.5)

        # -------- 0x02: Ürün bilgisi --------
        rx = bms_send(0x02)
        if rx and len(rx) > 10:
            payload = bytes(rx[9:-1]).decode(errors="ignore").strip()
            print(f"    ✅ Cevap alındı (Ürün: {payload})")
            modbus_data["bms_product_info"] = payload
        else:
            print("    ⚠️ Cevap yok (Cmd=0x02)")
        time.sleep(0.5)

        # -------- 0x20: RTC --------
        rx = bms_send(0x20)
        if rx and len(rx) >= 14:
            d = rx[6:-1]
            year, month, day = d[0] + 2000, d[1], d[2]
            hour, minute, second = d[3], d[4], d[5]
            print(f"    ✅ Cevap alındı (RTC: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d})")
            modbus_data["bms_rtc"] = f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
        else:
            print("    ⚠️ Cevap yok (Cmd=0x20)")
        time.sleep(0.5)

        # -------- MOS durumları --------
        for cmd, label in [(0x2D, "Deşarj"), (0x2E, "Şarj")]:
            rx = bms_send(cmd)
            if rx and len(rx) >= 8:
                state = "ON" if rx[7] == 1 else "OFF"
                print(f"    ✅ Cevap alındı ({label} MOS: {state})")
                modbus_data[f"bms_{'dischg' if cmd == 0x2D else 'chg'}_mos"] = state
            else:
                print(f"    ⚠️ Cevap yok (Cmd=0x{cmd:02X})")
            time.sleep(0.5)

        modbus_data["bms_status"] = "OK"

    except Exception as e:
        print(f"    ❌ BMS okuma hatası: {e}")

# ========================================
# MPPT OKUMA (Slave 0x0A)
# ========================================

def read_mppt():
    """MPPT (Lumiax) verilerini oku"""
    print("  ☀️ MPPT okuma...")
    
    try:
        # Batarya Voltajı (Register 0x3046, FC 04)
        tx = bytes([SLAVE_MPPT, 0x04, 0x30, 0x46, 0x00, 0x01])
        tx = add_crc(tx)
        rx = send_receive(tx)
        
        if rx and len(rx) >= 7 and check_crc(rx):
            voltage_raw = (rx[3] << 8) | rx[4]
            modbus_data['mppt_battery_voltage'] = voltage_raw / 100.0
            print(f"    ✅ MPPT Bat Voltaj: {modbus_data['mppt_battery_voltage']:.2f}V")
        else:
            print(f"    ⚠️ MPPT voltaj okunamadı")
        
        time.sleep(0.1)
        
        # Batarya Akımı (Register 0x3047, FC 04)
        tx = bytes([SLAVE_MPPT, 0x04, 0x30, 0x47, 0x00, 0x01])
        tx = add_crc(tx)
        rx = send_receive(tx)
        
        if rx and len(rx) >= 7 and check_crc(rx):
            current_raw = (rx[3] << 8) | rx[4]
            # İşaretli
            if current_raw > 32767:
                current_raw -= 65536
            modbus_data['mppt_battery_current'] = current_raw / 100.0
            print(f"    ✅ MPPT Bat Akım: {modbus_data['mppt_battery_current']:.2f}A")
        else:
            print(f"    ⚠️ MPPT akım okunamadı")
        
        time.sleep(0.1)
        
        # PV Voltajı (Register 0x304E, FC 04)
        tx = bytes([SLAVE_MPPT, 0x04, 0x30, 0x4E, 0x00, 0x01])
        tx = add_crc(tx)
        rx = send_receive(tx)
        
        if rx and len(rx) >= 7 and check_crc(rx):
            pv_voltage_raw = (rx[3] << 8) | rx[4]
            modbus_data['mppt_pv_voltage'] = pv_voltage_raw / 100.0
            print(f"    ✅ MPPT PV Voltaj: {modbus_data['mppt_pv_voltage']:.2f}V")
        else:
            print(f"    ⚠️ MPPT PV voltaj okunamadı")
        
        time.sleep(0.1)
        
        # PV Akımı (Register 0x304F, FC 04)
        tx = bytes([SLAVE_MPPT, 0x04, 0x30, 0x4F, 0x00, 0x01])
        tx = add_crc(tx)
        rx = send_receive(tx)
        
        if rx and len(rx) >= 7 and check_crc(rx):
            pv_current_raw = (rx[3] << 8) | rx[4]
            modbus_data['mppt_pv_current'] = pv_current_raw / 100.0
            print(f"    ✅ MPPT PV Akım: {modbus_data['mppt_pv_current']:.2f}A")
        else:
            print(f"    ⚠️ MPPT PV akım okunamadı")
            
    except Exception as e:
        print(f"    ❌ MPPT okuma hatası: {e}")

# ========================================
# ÇEVRE SENSÖRÜ OKUMA (Slave 0x7B)
# ========================================

def read_env_sensor():
    """Çevre sensörü verilerini oku (IEEE754 Float)"""
    print("  🌡️ Çevre sensörü okuma...")
    
    try:
        # CO2 (Register 0x0008, FC 03, 2 register = 4 byte IEEE754)
        tx = bytes([SLAVE_ENV, 0x03, 0x00, 0x08, 0x00, 0x02])
        tx = add_crc(tx)
        rx =================
# ANA OKUMA FONKSİYONU
# ========================================

def read_all_devices():
    """Tüm cihazları oku"""
    print(f"\n📡 Modbus okuma başlıyor... [{datetime.now().strftime('%H:%M:%S')}]")
    
    # BMS oku
    read_bms()
    time.sleep(0.2)
    
    # MPPT oku
    read_mppt()
    time.sleep(0.2)
    
    # Çevre sensörü oku
    read_env_sensor()
    time.sleep(0.2)
    
    # LDR oku
    read_ldr()
    
    # Son güncelleme zamanı
    modbus_data['last_update'] = datetime.now().isoformat()
    
    print("")

# ========================================
# VERİ KAYDETME
# ========================================

def save_data():
    """Verileri JSON'a kaydet"""
    try:
        with open(MODBUS_DATA_FILE, 'w') as f:
            json.dump(modbus_data, f, indent=2)
        print(f"💾 Veri kaydedildi: {MODBUS_DATA_FILE}")
    except Exception as e:
        print(f"⚠️ Veri kaydetme hatası: {e}")

# ========================================
# ANA DÖNGÜ
# ========================================

def main():
    """Ana program"""
    print("=" * 60)
    print("🚀 nuGateway Modbus Reader (RAW Serial)")
    print("=" * 60)
    print(f"Serial Port: {SERIAL_PORT}")
    print(f"Baud Rate: {BAUDRATE}")
    print(f"Okuma Periyodu: {READ_INTERVAL} saniye")
    print("=" * 60)
    print("")
    
    # Serial port aç
    if not open_serial():
        return
    
    print("🔄 Ana döngü başlıyor...")
    print("   Ctrl+C ile durdurun\n")
    
    try:
        while True:
            # Tüm cihazları oku
            read_all_devices()
            
            # Verileri kaydet
            save_data()
            
            # Bekle
            time.sleep(READ_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Modbus Reader durduruluyor...")
    finally:
        close_serial()
        print("=" * 60)

if __name__ == '__main__':
    main()