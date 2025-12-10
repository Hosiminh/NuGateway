#!/usr/bin/env python3
"""
MODBUS RTU ADRES TARAYICI
- 0-255 arası tüm adresleri tarar
- CRC-16 otomatik hesaplanır
- Her turda TX/RX paketleri gösterilir
- 1500ms timeout (yavaş cihazlar için)
"""

import serial
import time
import sys

# ==================== AYARLAR ====================
PORT = '/dev/ttyUSB0'  # Windows: 'COM3', 'COM4' vs.
BAUDRATE = 9600
TIMEOUT = 1.5  # 1500ms timeout

# Modbus Register Ayarları
FUNCTION_CODE = 0x04      # 0x03: Holding, 0x04: Input
START_ADDRESS = 0x3046    # Okunacak register
QUANTITY = 0x0001         # Register sayısı

# Timing
WAIT_AFTER_TX = 0.1       # TX sonrası bekleme (100ms)
WAIT_BETWEEN = 0.05       # Sorgular arası (50ms)

# ==================== CRC-16 MODBUS ====================
def modbus_crc16(data):
    """
    Modbus CRC-16 hesaplama
    Polynomial: 0xA001, Init: 0xFFFF
    Return: Little-endian CRC bytes
    """
    MODBUS_CRC_INIT = 0xFFFF
    MODBUS_CRC_POLY = 0xA001
    
    crc = MODBUS_CRC_INIT
    
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= MODBUS_CRC_POLY
            else:
                crc >>= 1
    
    # Little-endian: Low byte first, High byte second
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

# ==================== MODBUS PAKETİ OLUŞTUR ====================
def create_modbus_packet(slave_address, function_code, register_address, quantity):
    """
    Modbus RTU Query paketi oluşturur
    """
    packet = bytearray()
    
    # Slave Address (1 byte)
    packet.append(slave_address)
    
    # Function Code (1 byte)
    packet.append(function_code)
    
    # Register Address (2 bytes, Big-Endian)
    packet.append((register_address >> 8) & 0xFF)  # High byte
    packet.append(register_address & 0xFF)         # Low byte
    
    # Quantity (2 bytes, Big-Endian)
    packet.append((quantity >> 8) & 0xFF)          # High byte
    packet.append(quantity & 0xFF)                 # Low byte
    
    # CRC hesapla ve ekle (2 bytes, Little-Endian)
    crc = modbus_crc16(packet)
    packet.extend(crc)
    
    return bytes(packet)

# ==================== HEX YAZDIRMA ====================
def bytes_to_hex(data):
    """
    Bytes'ı hex string'e çevirir
    Örnek: b'\x01\x04' -> "01 04"
    """
    if not data:
        return ""
    return ' '.join(f'{b:02X}' for b in data)

# ==================== CRC DOĞRULAMA ====================
def verify_crc(response):
    """
    Response'un CRC'sini kontrol eder
    """
    if len(response) < 3:
        return False
    
    data = response[:-2]
    received_crc = response[-2:]
    calculated_crc = modbus_crc16(data)
    
    return received_crc == calculated_crc

# ==================== TARAMA FONKSİYONU ====================
def scan_modbus_addresses(start_addr=0, end_addr=255):
    """
    Modbus adreslerini tarar
    """
    found_devices = []
    
    print("\n" + "=" * 90)
    print(f"{'MODBUS RTU ADRES TARAYICI':^90}")
    print("=" * 90)
    print(f"Port           : {PORT}")
    print(f"Baudrate       : {BAUDRATE}")
    print(f"Timeout        : {int(TIMEOUT * 1000)}ms")
    print(f"Function Code  : 0x{FUNCTION_CODE:02X}")
    print(f"Register       : 0x{START_ADDRESS:04X}")
    print(f"Quantity       : {QUANTITY}")
    print(f"Tarama Aralığı : {start_addr} - {end_addr}")
    print("=" * 90)
    print()
    
    try:
        # Serial port aç
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            timeout=TIMEOUT,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )
        
        print(f"{'ADRES':<8} {'TX (Gönderilen)':<30} {'RX (Alınan)':<30} {'DURUM':<20}")
        print("-" * 90)
        
        start_time = time.time()
        
        # Her adresi tara
        for address in range(start_addr, end_addr + 1):
            
            # Modbus paketi oluştur
            tx_packet = create_modbus_packet(address, FUNCTION_CODE, START_ADDRESS, QUANTITY)
            
            # Buffer temizle
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            # TX zamanını kaydet
            tx_time = time.time()
            
            # Paketi gönder
            ser.write(tx_packet)
            
            # TX sonrası kısa bekleme
            time.sleep(WAIT_AFTER_TX)
            
            # Cevap bekle
            rx_packet = ser.read(100)
            
            # RX zamanını kaydet
            rx_time = time.time()
            response_time_ms = (rx_time - tx_time) * 1000
            
            # TX paketini göster
            tx_hex = bytes_to_hex(tx_packet)
            addr_str = f"{address:3d} (0x{address:02X})"
            
            # Cevap var mı?
            if rx_packet and len(rx_packet) >= 5:
                rx_hex = bytes_to_hex(rx_packet)
                
                # CRC kontrol et
                if verify_crc(rx_packet):
                    status = f"✓ BULUNDU ({response_time_ms:.0f}ms)"
                    print(f"{addr_str:<8} {tx_hex:<30} {rx_hex:<30} {status:<20}")
                    
                    # Bulunan cihazı kaydet
                    found_devices.append({
                        'address': address,
                        'tx': tx_packet,
                        'rx': rx_packet,
                        'response_time_ms': response_time_ms
                    })
                    
                else:
                    # CRC hatalı
                    status = f"⚠ CRC HATASI"
                    print(f"{addr_str:<8} {tx_hex:<30} {rx_hex:<30} {status:<20}")
            else:
                # Cevap yok
                status = "✗ CEVAP YOK"
                print(f"{addr_str:<8} {tx_hex:<30} {'-':<30} {status:<20}")
            
            # Progress göster (her 10 adresste bir)
            if (address - start_addr + 1) % 10 == 0:
                elapsed = time.time() - start_time
                remaining = (end_addr - address) * (elapsed / (address - start_addr + 1))
                sys.stdout.write(f"\rİlerleme: {address - start_addr + 1}/{end_addr - start_addr + 1} | "
                               f"Bulunan: {len(found_devices)} | "
                               f"Kalan: ~{remaining:.0f}s    ")
                sys.stdout.flush()
            
            # Sorgular arası bekleme
            time.sleep(WAIT_BETWEEN)
        
        # Progress satırını temizle
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        
        total_time = time.time() - start_time
        
        # Sonuç özeti
        print()
        print("=" * 90)
        print(f"{'TARAMA TAMAMLANDI':^90}")
        print("=" * 90)
        print(f"Toplam Süre     : {total_time:.1f} saniye")
        print(f"Taranan Adres   : {end_addr - start_addr + 1} adet")
        print(f"Bulunan Cihaz   : {len(found_devices)} adet")
        print("=" * 90)
        
        # Bulunan cihazları detaylı göster
        if found_devices:
            print()
            print(f"{'BULUNAN CİHAZLAR - DETAY':^90}")
            print("=" * 90)
            
            for idx, device in enumerate(found_devices, 1):
                print(f"\n{idx}. CİHAZ:")
                print(f"   Adres         : {device['address']} (0x{device['address']:02X})")
                print(f"   Response Time : {device['response_time_ms']:.1f}ms")
                print(f"   TX Paketi     : {bytes_to_hex(device['tx'])}")
                print(f"   RX Paketi     : {bytes_to_hex(device['rx'])}")
                
                # Data parse et (eğer varsa)
                if len(device['rx']) > 4:
                    byte_count = device['rx'][2]
                    if len(device['rx']) >= 3 + byte_count + 2:
                        data = device['rx'][3:3+byte_count]
                        print(f"   Data          : {bytes_to_hex(data)}")
                        
                        # 2 byte'lık değeri oku
                        if len(data) >= 2:
                            value = int.from_bytes(data[:2], byteorder='big')
                            print(f"   Değer (Dec)   : {value}")
                            print(f"   Değer (Hex)   : 0x{value:04X}")
            
            print("\n" + "=" * 90)
        else:
            print()
            print("⚠ HİÇBİR CİHAZ BULUNAMADI!")
            print()
            print("Kontrol Listesi:")
            print("  1. Port adresi doğru mu?")
            print("  2. Baudrate doğru mu?")
            print("  3. RS485 bağlantıları doğru mu? (A-A, B-B)")
            print("  4. Cihaz çalışıyor mu?")
            print("  5. Termination dirençleri var mı?")
            print("=" * 90)
        
        ser.close()
        print()
        return found_devices
        
    except serial.SerialException as e:
        print(f"\n✗ SERIAL PORT HATASI: {e}")
        print("\nÇözümler:")
        print("  • Linux: sudo python3 script.py")
        print("  • Windows: Yönetici olarak çalıştır")
        print("  • Başka program portu kullanıyor olabilir")
        return []
    
    except KeyboardInterrupt:
        print("\n\n⚠ Kullanıcı tarafından durduruldu!")
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print(f"Bulunan: {len(found_devices)} cihaz\n")
        return found_devices
    
    except Exception as e:
        print(f"\n✗ HATA: {e}")
        import traceback
        traceback.print_exc()
        if 'ser' in locals() and ser.is_open:
            ser.close()
        return []

# ==================== TEK ADRES TEST ====================
def test_single_address(address):
    """
    Tek bir adresi test eder
    """
    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            timeout=TIMEOUT,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )
        
        print("\n" + "=" * 90)
        print(f"TEK ADRES TEST - Adres: {address} (0x{address:02X})")
        print("=" * 90)
        
        # Paket oluştur
        tx_packet = create_modbus_packet(address, FUNCTION_CODE, START_ADDRESS, QUANTITY)
        
        print(f"Function Code  : 0x{FUNCTION_CODE:02X}")
        print(f"Register       : 0x{START_ADDRESS:04X}")
        print(f"Quantity       : {QUANTITY}")
        print(f"Timeout        : {int(TIMEOUT * 1000)}ms")
        print()
        print(f"TX Paketi      : {bytes_to_hex(tx_packet)}")
        print()
        print("Gönderiliyor...")
        
        # Buffer temizle
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Gönder
        tx_time = time.time()
        ser.write(tx_packet)
        time.sleep(WAIT_AFTER_TX)
        
        # Bekle
        rx_packet = ser.read(100)
        rx_time = time.time()
        response_time_ms = (rx_time - tx_time) * 1000
        
        print(f"Beklendi: {response_time_ms:.1f}ms")
        print()
        
        if rx_packet:
            print(f"RX Paketi      : {bytes_to_hex(rx_packet)}")
            
            if verify_crc(rx_packet):
                print(f"CRC            : ✓ GEÇERLİ")
                
                # Data parse et
                if len(rx_packet) > 4:
                    byte_count = rx_packet[2]
                    if len(rx_packet) >= 3 + byte_count + 2:
                        data = rx_packet[3:3+byte_count]
                        print(f"Data           : {bytes_to_hex(data)}")
                        
                        if len(data) >= 2:
                            value = int.from_bytes(data[:2], byteorder='big')
                            print(f"Değer (Dec)    : {value}")
                            print(f"Değer (Hex)    : 0x{value:04X}")
            else:
                print(f"CRC            : ✗ HATALI")
        else:
            print(f"RX Paketi      : -")
            print(f"Durum          : ✗ CEVAP YOK")
        
        print("=" * 90)
        print()
        
        ser.close()
        
    except Exception as e:
        print(f"\n✗ HATA: {e}\n")

# ==================== CRC TEST ====================
def test_crc():
    """
    CRC hesaplamasını test eder
    """
    print("\n" + "=" * 90)
    print(f"{'MODBUS CRC-16 TEST':^90}")
    print("=" * 90)
    
    test_cases = [
        {
            'name': 'Standart Test',
            'data': bytes([0x01, 0x04, 0x30, 0x46, 0x00, 0x01]),
            'expected': bytes([0xDF, 0x1F])
        },
        {
            'name': 'Function 0x03',
            'data': bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x0A]),
            'expected': bytes([0xC5, 0xCD])
        },
    ]
    
    for test in test_cases:
        print(f"\n{test['name']}:")
        print(f"  Data     : {bytes_to_hex(test['data'])}")
        
        calculated = modbus_crc16(test['data'])
        print(f"  Expected : {bytes_to_hex(test['expected'])}")
        print(f"  Calculated: {bytes_to_hex(calculated)}")
        
        if calculated == test['expected']:
            print(f"  Sonuç    : ✓ DOĞRU")
        else:
            print(f"  Sonuç    : ✗ HATALI")
        
        full_packet = test['data'] + calculated
        print(f"  Tam Paket: {bytes_to_hex(full_packet)}")
    
    print("\n" + "=" * 90 + "\n")

# ==================== MAIN ====================
def main():
    """
    Ana fonksiyon
    """
    print("\n╔════════════════════════════════════════════════════════════════════════════╗")
    print("║              MODBUS RTU ADRES TARAYICI - Python Edition                   ║")
    print("╚════════════════════════════════════════════════════════════════════════════╝")
    
    if len(sys.argv) == 1:
        # Argüman yok - tüm adresleri tara
        scan_modbus_addresses(0, 255)
        
    elif len(sys.argv) == 2:
        arg = sys.argv[1].lower()
        
        if arg == 'test':
            # CRC test
            test_crc()
        else:
            # Tek adres test
            try:
                address = int(sys.argv[1])
                if 0 <= address <= 255:
                    test_single_address(address)
                else:
                    print("✗ Adres 0-255 arasında olmalı!")
            except ValueError:
                print("✗ Geçersiz adres!")
                
    elif len(sys.argv) == 3:
        # Aralık tarama
        try:
            start = int(sys.argv[1])
            end = int(sys.argv[2])
            if 0 <= start <= 255 and 0 <= end <= 255 and start <= end:
                scan_modbus_addresses(start, end)
            else:
                print("✗ Geçersiz aralık!")
        except ValueError:
            print("✗ Geçersiz parametre!")
    else:
        print("\nKullanım:")
        print("  python3 scanner.py              # Tüm adresleri tara (0-255)")
        print("  python3 scanner.py 1 50         # Belirli aralık (1-50)")
        print("  python3 scanner.py 17           # Tek adres test")
        print("  python3 scanner.py test         # CRC testi\n")

if __name__ == "__main__":
    main()
