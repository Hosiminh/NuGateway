import time
import subprocess
import json
from settings_manager import load_settings  # settings.json'dan ayarları okumak için

INTERVAL_SECONDS = 10  # fallback default

def run_reader():
    while True:
        settings = load_settings()
        interval = int(settings.get("interval", INTERVAL_SECONDS))

        try:
            # modbus_reader.py scriptini çalıştırarak sensors.json'u güncelle
            subprocess.run(["python3", "modbus_reader.py"], check=True)
            print("✅ Veriler başarıyla okundu ve sensors.json dosyasına yazıldı.")
        except subprocess.CalledProcessError as e:
            print("❌ modbus_reader.py çalıştırılamadı:", e)

        time.sleep(interval)

if __name__ == "__main__":
    run_reader()
