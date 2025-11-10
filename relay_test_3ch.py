#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

# 3 Kanallı Waveshare RPi Relay Board pinleri
RELAY_PINS = {
    1: 26,  # CH1
    2: 20,  # CH2
    3: 21   # CH3
}

# GPIO kurulumu
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Tüm röle pinlerini output olarak ayarla ve başlangıçta kapat
for pin in RELAY_PINS.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)  # HIGH = Röle KAPALI

def relay_on(channel):
    """Röleyi aç (1-3 arası)"""
    if channel in RELAY_PINS:
        pin = RELAY_PINS[channel]
        GPIO.output(pin, GPIO.LOW)  # LOW = Röle AÇIK
        print(f"✅ Röle CH{channel} AÇILDI (Pin: BCM{pin})")
        return True
    else:
        print(f"❌ Geçersiz kanal: {channel}")
        return False

def relay_off(channel):
    """Röleyi kapat (1-3 arası)"""
    if channel in RELAY_PINS:
        pin = RELAY_PINS[channel]
        GPIO.output(pin, GPIO.HIGH)  # HIGH = Röle KAPALI
        print(f"⛔ Röle CH{channel} KAPANDI (Pin: BCM{pin})")
        return True
    else:
        print(f"❌ Geçersiz kanal: {channel}")
        return False

def relay_status():
    """Tüm rölelerin durumunu göster"""
    print("\n🎛️  Röle Durumları:")
    print("-" * 40)
    for ch, pin in RELAY_PINS.items():
        state = GPIO.input(pin)
        status = "⛔ KAPALI" if state else "✅ AÇIK"
        print(f"CH{ch} (BCM{pin}): {status}")
    print("-" * 40 + "\n")

def all_off():
    """Tüm röleleri kapat"""
    for pin in RELAY_PINS.values():
        GPIO.output(pin, GPIO.HIGH)
    print("⛔ Tüm röleler KAPANDI")

def all_on():
    """Tüm röleleri aç"""
    for pin in RELAY_PINS.values():
        GPIO.output(pin, GPIO.LOW)
    print("✅ Tüm röleler AÇILDI")

def test_sequence():
    """Sıralı test - her röleyi 3 saniye aç/kapa"""
    print("\n🔄 Röle testi başlıyor (3 saniye aralıkla)...")
    for ch in [1, 2, 3]:
        relay_on(ch)
        time.sleep(3)
        relay_off(ch)
        time.sleep(1)
    print("✅ Test tamamlandı!\n")

def cleanup():
    """GPIO pinlerini temizle"""
    all_off()
    GPIO.cleanup()
    print("🧹 GPIO temizlendi")

if __name__ == "__main__":
    try:
        print("=" * 50)
        print("🎛️  Waveshare RPi Relay Board (3 Kanal)")
        print("=" * 50)
        
        while True:
            print("\nSeçenekler:")
            print("1/2/3: Tekil röle kontrol")
            print("s    : Durum göster")
            print("t    : Sıralı test yap")
            print("a    : Tüm röleleri aç")
            print("k    : Tüm röleleri kapat")
            print("q    : Çıkış")
            
            choice = input("\nSeçim: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == 's':
                relay_status()
            elif choice == 't':
                test_sequence()
            elif choice == 'a':
                all_on()
            elif choice == 'k':
                all_off()
            elif choice in ['1', '2', '3']:
                ch = int(choice)
                print(f"\nRöle CH{ch} için:")
                print("1: AÇ | 0: KAPA | s: Durum")
                cmd = input("Komut: ").strip()
                if cmd == '1':
                    relay_on(ch)
                elif cmd == '0':
                    relay_off(ch)
                elif cmd == 's':
                    state = GPIO.input(RELAY_PINS[ch])
                    status = "⛔ KAPALI" if state else "✅ AÇIK"
                    print(f"CH{ch}: {status}")
            else:
                print("❌ Geçersiz seçim")
    
    except KeyboardInterrupt:
        print("\n⚠️  Ctrl+C ile durduruldu")
    finally:
        cleanup()