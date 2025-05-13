from pymodbus.client import ModbusSerialClient
import struct
import json
import time
from relay_control import apply_logic

SENSOR_FILE = "sensors.json"

def load_settings():
    with open("settings.json") as f:
        return json.load(f)

def read_float32_ieee754(registers):
    combined = (registers[0] << 16) | registers[1]
    return struct.unpack('>f', combined.to_bytes(4, byteorder='big'))[0]

def classify_air_quality(pm2_5, co2):
    score = 0
    if pm2_5 > 55: score += 2
    elif pm2_5 > 35: score += 1
    if co2 > 2000: score += 2
    elif co2 > 1200: score += 1

    levels = {
        0: ("Mükemmel", 0),
        1: ("Orta", 25),
        2: ("Düşük kalite", 50),
        3: ("Kötü", 75),
        4: ("Sağlıksız", 100)
    }
    return levels.get(score, ("Bilinmiyor", 0))

def estimate_weather(temp, humidity, lux):
    if temp > 25 and humidity < 50 and lux > 20000:
        return "Güneşli ve sıcak"
    elif temp < 10 and humidity > 70 and lux < 10000:
        return "Soğuk ve yağışlı"
    elif 10 <= temp <= 20 and 50 <= humidity <= 70 and 10000 <= lux <= 20000:
        return "Serin ve parçalı bulutlu"
    elif 15 <= temp <= 25 and humidity > 70 and lux < 15000:
        return "Ilık ve nemli"
    else:
        return "Kararsız hava koşulları"

def read_sensors():
    settings = load_settings()
    port = settings.get("serial_port", "/tmp/ttySIM1")
    baudrate = int(settings.get("baudrate", 9600))

    client = ModbusSerialClient(
        method="rtu",
        port=port,
        baudrate=baudrate,
        timeout=2,
        stopbits=int(settings.get("stop_bits", 1)),
        bytesize=int(settings.get("data_bits", 8)),
        parity=settings.get("parity", "N")
    )

    if not client.connect():
        print("❌ Modbus bağlantısı başarısız!")
        return

    result = {}

    # --- LDR ---
    try:
        r = client.read_holding_registers(address=0x0000, count=2, slave=1)
        if not r.isError():
            lux = (r.registers[0] << 16) | r.registers[1]
            result["ldr_lux"] = lux
            result["is_dark"] = lux < 20000
        else:
            print("LDR:", r)
    except Exception as e:
        print("LDR Exception:", e)

    # --- ENVIRONMENTAL SENSOR ---
    try:
        co2 = client.read_holding_registers(0x0008, 2, slave=123)
        temp = client.read_holding_registers(0x000E, 2, slave=123)
        hum = client.read_holding_registers(0x0010, 2, slave=123)
        pm25 = client.read_holding_registers(0x000A, 2, slave=123)
        pm10 = client.read_holding_registers(0x000C, 2, slave=123)
        illumination = client.read_holding_registers(0x0012, 2, slave=123)

        if all(not x.isError() for x in [co2, temp, hum, pm25, pm10, illumination]):
            co2_val = read_float32_ieee754(co2.registers)
            temp_val = read_float32_ieee754(temp.registers)
            hum_val = read_float32_ieee754(hum.registers)
            pm25_val = read_float32_ieee754(pm25.registers)
            pm10_val = read_float32_ieee754(pm10.registers)
            illum_val = read_float32_ieee754(illumination.registers)

            result["co2"] = round(co2_val, 2)
            result["temperature"] = round(temp_val, 2)
            result["humidity"] = round(hum_val, 2)
            result["pm2_5"] = round(pm25_val, 2)
            result["pm10"] = round(pm10_val, 2)
            result["illumination"] = round(illum_val, 2)

            air_text, air_score = classify_air_quality(pm25_val, co2_val)
            result["air_quality"] = air_text
            result["air_quality_score"] = air_score

            lux = result.get("ldr_lux", 0)
            result["weather_status"] = estimate_weather(temp_val, hum_val, lux)
        else:
            print("EnvSensor: modbus read error")
    except Exception as e:
        print("EnvSensor Exception:", e)

    # --- MPPT ---
    try:
        pv_v = client.read_input_registers(0x3000, 1, slave=3)
        pv_c = client.read_input_registers(0x3001, 1, slave=3)
        if not pv_v.isError() and not pv_c.isError():
            volt = pv_v.registers[0] / 100.0
            curr = pv_c.registers[0] / 100.0
            result["pv_voltage"] = volt
            result["pv_current"] = curr
            result["pv_power"] = round(volt * curr, 2)
            result["mppt_status"] = "Charging"
        else:
            print("MPPT: modbus read error")
    except Exception as e:
        print("MPPT Exception:", e)

    # --- PIR ---
    try:
        pir = client.read_holding_registers(0x0006, 1, slave=2)
        if not pir.isError():
            pir_value = pir.registers[0]
            result["motion_detected"] = pir_value == 1
            result["display_should_be_on"] = pir_value == 1
        else:
            print("PIR: modbus read error")
    except Exception as e:
        print("PIR Exception:", e)

    # --- BMS ---
    try:
        regs = {}
        addresses = {
            "battery_voltage": 0x3004,
            "battery_current": 0x3005,
            "battery_soc": 0x3020,
            "battery_soh": 0x3021,
            "battery_temp": 0x3022,
            "discharge_time": 0x3023,
            "charge_time": 0x3024
        }
        for key, addr in addresses.items():
            r = client.read_input_registers(addr, 1, slave=4)
            if not r.isError():
                regs[key] = r.registers[0]
            else:
                print(f"BMS {key}: read error")

        if "battery_voltage" in regs and "battery_current" in regs:
            bv = regs["battery_voltage"] / 100.0
            bc = regs["battery_current"] / 100.0
            result["battery_voltage"] = bv
            result["battery_current"] = bc
            result["battery_power"] = round(bv * bc, 2)

        result["battery_soc"] = regs.get("battery_soc")
        result["battery_soh"] = regs.get("battery_soh")
        if "battery_temp" in regs:
            result["battery_temp"] = regs["battery_temp"] / 10.0
        result["discharge_time"] = regs.get("discharge_time")
        result["charge_time"] = regs.get("charge_time")
        result["bms_low_power_mode"] = result.get("battery_soc", 100) < 30

    except Exception as e:
        print("BMS Exception:", e)

    client.close()

    with open(SENSOR_FILE, "w") as f:
        json.dump(result, f, indent=2)

    apply_logic(result)
    print("✅ Veriler sensors.json'a yazıldı ve röle kontrolü uygulandı.")

if __name__ == "__main__":
    while True:
        read_sensors()
        time.sleep(10)
