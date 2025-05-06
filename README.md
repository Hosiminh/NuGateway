# nuGateway

**nuGateway**, Modbus RTU üzerinden veri toplayan, Raspberry Pi 4 üzerinde çalışan ve HTML + Flask tabanlı modern bir arayüzle kullanıcıya sunan entegre bir gömülü gateway çözümüdür.

## Özellikler

- 📡 **Modbus RTU Desteği**  
  LDR sensörü, çevre sensörü, PIR sensörü ve MPPT şarj kontrol cihazı ile doğrudan seri port üzerinden haberleşme

- 🔌 **8 Kanal Röle Kontrolü**  
  GPIO (BCM) pinleri üzerinden 8 röle çıkışının izlenmesi ve kontrol edilmesi

- 🌐 **Web Tabanlı Dashboard**  
  Modern görünümlü `dashboard.html`, `devices.html` ve `settings.html` sayfaları ile canlı veri takibi ve yapılandırma

- 📁 **JSON Tabanlı Veri Saklama**  
  Röle durumları ve sensör verileri yerel JSON dosyalarında tutulur

## Kurulum

### Gereksinimler

- Raspberry Pi 4 (Raspbian OS)
- Python 3.7+
- Modbus cihazlar için USB → RS485 dönüştürücü

### Bağımlılıklar

```bash
pip install -r requirements.txt

nuGateway/
├── app.py               # Flask uygulama başlangıç dosyası
├── modbus_reader.py     # Sensör verilerini okuma mantığı
├── relay_control.py     # Röle durumlarını yönetme
├── update_loop.py       # Belirli aralıklarla sensör verilerini güncelleme
├── templates/
│   ├── dashboard.html
│   ├── devices.html
│   └── settings.html
├── static/
│   ├── styles.css
│   └── main.js
├── sensors.json         # Sensör verileri (otomatik güncellenir)
├── relay_states.json    # Röle durumları
├── gateway_settings.json # Konfigürasyon ayarları (ör: baudrate)
└── requirements.txt     # Python bağımlılıkları
