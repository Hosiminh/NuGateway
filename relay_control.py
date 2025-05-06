import json
import os

STATE_FILE = "relay_states.json"
RELAY_COUNT = 8

# GPIO pin atamaları (BCM modunda)
RELAY_PINS = [5, 6, 13, 19, 26, 16, 20, 21]

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    for pin in RELAY_PINS:
        GPIO.setup(pin, GPIO.OUT)
except ImportError:
    GPIO = None
    print("GPIO kütüphanesi yüklü değil. Simülasyon modunda çalışıyor.")

# İlk yükleme veya varsayılan durum üret
def load_states():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            raw = json.load(f)
        # backward compatibility
        if isinstance(raw, dict):  # eski {"0": true} formatı
            return [{"state": raw.get(str(i), False)} for i in range(RELAY_COUNT)]
        return raw
    # yoksa sıfırdan oluştur
    return [{"state": False} for _ in range(RELAY_COUNT)]

# Dosyaya yaz
def save_states(states):
    with open(STATE_FILE, "w") as f:
        json.dump(states, f)

# Röleyi aç/kapat
def toggle_relay(index):
    states = load_states()
    new_state = not states[index]["state"]
    states[index]["state"] = new_state

    # GPIO set et
    if GPIO:
        GPIO.output(RELAY_PINS[index], GPIO.HIGH if new_state else GPIO.LOW)

    save_states(states)
    return new_state

# Tüm röle durumlarını getir
def get_relay_states():
    return load_states()
