# NuGateway Patch Artifacts

Date: 2025-10-22T13:34:57.768872

Applied changes:

- settings.html: Fixed endpoints to /api/*
- mppt_control.html: Switched success checks to status==="ok"
- devices.html: Injected Slave ID legend (non-destructive)
- config.py: Added defaults for use_simulator=False, modbus_in_flask=False
- modbus_reader.py: Injected USE_SIM from config_manager
- modbus_reader.py: Added helper functions for SIM/REAL mapping
- modbus_reader.py: Applied SIM/REAL register and slave-id mapping for LDR/ENV/MPPT
- app.py: Added modbus_in_flask flag to avoid serial port clashes

Usage tips:

1) Test simülatörde:
   - settings → Port: /tmp/ttySIM0
   - Settings.json → "use_simulator": true, "modbus_in_flask": false
   - modbus_reader.py'yi service olarak çalıştırın; Flask sadece sensors.json okuyacak.

2) Gerçek RS485'te:
   - Port: /dev/ttyAMA0 (veya USB-Serial ise /dev/ttyUSB0)
   - "use_simulator": false
   - İsterseniz "modbus_in_flask": true yaparak Modbus'ı Flask içinde de çalıştırabilirsiniz (tek proses!).

3) mppt_control.html artık "status==='ok'" arıyor; backend JSON { "status":"ok" } döndürüyor olmalı.
4) devices.html içine Slave ID legend eklendi (yapıya dokunmadan).