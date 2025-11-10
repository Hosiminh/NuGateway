#!/usr/bin/env python3
import serial
import time

# Seri port ayarları
PORT = '/dev/ttyUSB0'
BAUDRATE = 9600
TIMEOUT = 1

# Gönderilecek hex data
hex_data = "01 06 90 54 00 46 64 E8"

# Hex string'i byte'a çevir
data_bytes = bytes.fromhex(hex_data.replace(" ", ""))

print(f"📡 Modbus RTU Mesajı Gönderiliyor...")
print(f"Port: {PORT}")
print(f"Baudrate: {BAUDRATE}")
print(f"Data (HEX): {hex_data}")
print(f"Data (Bytes): {data_bytes.hex(' ').upper()}")

try:
    # Seri port aç
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=TIMEOUT
    )
    
    print(f"✅ Port açıldı: {ser.name}")
    
    # Veriyi gönder
    bytes_written = ser.write(data_bytes)
    print(f"📤 {bytes_written} byte gönderildi")
    
    # Kısa bekleme
    time.sleep(0.1)
    
    # Cevap bekle (varsa)
    if ser.in_waiting > 0:
        response = ser.read(ser.in_waiting)
        print(f"📥 Cevap alındı ({len(response)} byte): {response.hex(' ').upper()}")
    else:
        print("📥 Cevap yok (normal olabilir)")
    
    # Port kapat
    ser.close()
    print("✅ İşlem tamamlandı")
    
except serial.SerialException as e:
    print(f"❌ Seri port hatası: {e}")
except Exception as e:
    print(f"❌ Hata: {e}")