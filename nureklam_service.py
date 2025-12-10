#!/usr/bin/env python3
"""
NuReklam Display Service
- 3 röleyi açar (display, load1, load2)
- Ekranı dikey yapar
- Videoyu loop oynatır
- 2 saat sonra röleleri kapatır
"""

import subprocess
import time
import signal
import sys
import os
import logging
from datetime import datetime, timedelta

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ayarlar
VIDEO_PATH = "/home/cafer/Desktop/NuGateway/videos/NuReklam.mp4"
RELAY_PINS = {"display": 6, "load1": 13, "load2": 19}  # Açılacak röleler
AUTO_OFF_HOURS = 2  # 2 saat sonra kapat

# GPIO Setup
try:
    from gpiozero import OutputDevice
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("GPIO not available")


class NuReklamService:
    def __init__(self):
        self.running = True
        self.relays = {}
        self.player_process = None
        self.start_time = datetime.now()
        self.auto_off_time = self.start_time + timedelta(hours=AUTO_OFF_HOURS)
        
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        logger.info("Kapatma sinyali alındı...")
        self.running = False
    
    def init_relays(self):
        """Röleleri başlat"""
        if not GPIO_AVAILABLE:
            logger.warning("GPIO yok, mock modda çalışıyor")
            return
        
        for name, pin in RELAY_PINS.items():
            try:
                self.relays[name] = OutputDevice(pin, active_high=True, initial_value=False)
                logger.info(f"Röle '{name}' (GPIO {pin}) hazır")
            except Exception as e:
                logger.error(f"Röle '{name}' başlatılamadı: {e}")
    
    def relays_on(self):
        """Tüm röleleri aç"""
        logger.info("🔌 Röleler açılıyor...")
        for name, relay in self.relays.items():
            try:
                relay.on()
                logger.info(f"  ✅ {name}: ON")
            except Exception as e:
                logger.error(f"  ❌ {name} açılamadı: {e}")
    
    def relays_off(self):
        """Tüm röleleri kapat"""
        logger.info("🔌 Röleler kapatılıyor...")
        for name, relay in self.relays.items():
            try:
                relay.off()
                logger.info(f"  ⭕ {name}: OFF")
            except Exception as e:
                logger.error(f"  ❌ {name} kapatılamadı: {e}")
    
    def rotate_screen(self):
        """Ekranı dikey yap"""
        logger.info("🖥️ Ekran dikey yapılıyor...")
        try:
            # Wayland için
            subprocess.run(
                ["wlr-randr", "--output", "HDMI-A-1", "--transform", "90"],
                timeout=10,
                env={**os.environ, "WAYLAND_DISPLAY": "wayland-1"}
            )
            logger.info("  ✅ Ekran dikey yapıldı")
        except Exception as e:
            logger.error(f"  ❌ Ekran döndürülemedi: {e}")
    
    def start_video(self):
        """Videoyu başlat"""
        if self.player_process and self.player_process.poll() is None:
            return  # Zaten çalışıyor
        
        logger.info("🎬 Video başlatılıyor...")
        try:
            self.player_process = subprocess.Popen([
                "mpv",
                "--fullscreen",
                "--loop-file=inf",
                "--no-terminal",
                "--no-osc",
                "--no-input-default-bindings",
                VIDEO_PATH
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"  ✅ Video oynatılıyor (PID: {self.player_process.pid})")
        except Exception as e:
            logger.error(f"  ❌ Video başlatılamadı: {e}")
    
    def stop_video(self):
        """Videoyu durdur"""
        if self.player_process:
            try:
                self.player_process.terminate()
                self.player_process.wait(timeout=5)
                logger.info("🎬 Video durduruldu")
            except:
                self.player_process.kill()
            self.player_process = None
    
    def run(self):
        """Ana döngü"""
        logger.info("=" * 50)
        logger.info("🚀 NuReklam Service Başlatılıyor")
        logger.info(f"⏰ Otomatik kapanma: {self.auto_off_time.strftime('%H:%M:%S')}")
        logger.info("=" * 50)
        
        # 1. Röleleri başlat ve aç
        self.init_relays()
        self.relays_on()
        
        # 2. Ekranı dikey yap
        time.sleep(2)  # Ekran açılsın
        self.rotate_screen()
        
        # 3. Videoyu başlat
        time.sleep(1)
        self.start_video()
        
        # 4. Ana döngü
        while self.running:
            # Video çöktüyse yeniden başlat
            if self.player_process and self.player_process.poll() is not None:
                logger.warning("Video durmuş, yeniden başlatılıyor...")
                self.start_video()
            
            # 2 saat kontrolü
            if datetime.now() >= self.auto_off_time:
                logger.info("⏰ 2 saat doldu! Sistem kapatılıyor...")
                break
            
            # Kalan süreyi göster (her 10 dakikada bir)
            remaining = (self.auto_off_time - datetime.now()).total_seconds()
            if int(remaining) % 600 == 0:  # Her 10 dakika
                logger.info(f"⏱️ Kalan süre: {int(remaining // 60)} dakika")
            
            time.sleep(5)
        
        # Cleanup
        self.shutdown()
    
    def shutdown(self):
        """Temiz kapatma"""
        logger.info("🔄 Kapatılıyor...")
        self.stop_video()
        self.relays_off()
        logger.info("👋 NuReklam Service kapatıldı")


if __name__ == "__main__":
    service = NuReklamService()
    service.run()
