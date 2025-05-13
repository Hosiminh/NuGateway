from pymodbus.client import ModbusSerialClient
import struct
import json
import time
from relay_control import apply_logic

SENSOR_FILE = "sensors.json"


def load_settings():
    with open("gateway_settings.json") as f:
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
    port = settings.get("serial_port", "/dev/ttyUSB0")
    baudrate = int(settings.get("baudrate", 9600))

    client = ModbusSerialClient(
        method="rtu",
        port=port,
        baudrate=baudrate,
        timeout=1,
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
        r = client.read_holding_registers(address=0x0000, count=2, unit=1)
        lux = (r.registers[0] << 16) | r.registers[1]
        result["ldr_lux"] = lux
        result["is_dark"] = lux < 20000
    except Exception as e:
        print("LDR:", e)
        lux = 0

    # --- ENVIRONMENTAL SENSOR ---
    try:
        co2 = read_float32_ieee754(client.read_holding_registers(0x0008, 2, unit=123).registers)
        temp = read_float32_ieee754(client.read_holding_registers(0x000E, 2, unit=123).registers)
        hum = read_float32_ieee754(client.read_holding_registers(0x0010, 2, unit=123).registers)
        pm25 = read_float32_ieee754(client.read_holding_registers(0x000A, 2, unit=123).registers)
        pm10 = read_float32_ieee754(client.read_holding_registers(0x000C, 2, unit=123).registers)
        illumination = read_float32_ieee754(client.read_holding_registers(0x0012, 2, unit=123).registers)

        result["co2"] = round(co2, 2)
        result["temperature"] = round(temp, 2)
        result["humidity"] = round(hum, 2)
        result["pm2_5"] = round(pm25, 2)
        result["pm10"] = round(pm10, 2)
        result["illumination"] = round(illumination, 2)

        air_text, air_score = classify_air_quality(pm25, co2)
        result["air_quality"] = air_text
        result["air_quality_score"] = air_score

        result["weather_status"] = estimate_weather(temp, hum, lux)

    except Exception as e:
        print("EnvSensor:", e)

    # --- MPPT ---
    try:
        volt = client.read_input_registers(0x3000, 1, unit=3).registers[0] / 100.0
        curr = client.read_input_registers(0x3001, 1, unit=3).registers[0] / 100.0
        result["pv_voltage"] = volt
        result["pv_current"] = curr
        result["pv_power"] = round(volt * curr, 2)
        result["mppt_status"] = "Charging"
    except Exception as e:
        print("MPPT:", e)

    # --- PIR ---
    try:
        pir_value = client.read_holding_registers(0x0006, 1, unit=2).registers[0]
        result["motion_detected"] = pir_value == 1
        result["display_should_be_on"] = pir_value == 1
    except Exception as e:
        print("PIR:", e)

    # --- BMS ---
    try:
        bv = client.read_input_registers(0x3004, 1, unit=4).registers[0] / 100.0
        bc = client.read_input_registers(0x3005, 1, unit=4).registers[0] / 100.0
        result["battery_voltage"] = bv
        result["battery_current"] = bc
        result["battery_power"] = round(bv * bc, 2)
        result["battery_soc"] = client.read_input_registers(0x3020, 1, unit=4).registers[0]
        result["battery_soh"] = client.read_input_registers(0x3021, 1, unit=4).registers[0]
        result["battery_temp"] = client.read_input_registers(0x3022, 1, unit=4).registers[0] / 10.0
        result["discharge_time"] = client.read_input_registers(0x3023, 1, unit=4).registers[0]
        result["charge_time"] = client.read_input_registers(0x3024, 1, unit=4).registers[0]
        result["bms_low_power_mode"] = result["battery_soc"] < 30
    except Exception as e:
        print("BMS:", e)

    client.close()

    with open(SENSOR_FILE, "w") as f:
        json.dump(result, f, indent=2)

    apply_logic(result)
    print("✅ Veriler sensors.json'a yazıldı ve röle kontrolü uygulandı.")


if __name__ == "__main__":
    while True:
        read_sensors()
        time.sleep(10)
