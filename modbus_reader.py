from pymodbus.client.sync import ModbusSerialClient as ModbusClient
import struct
import json
import time

SENSOR_FILE = "sensors.json"

def load_settings():
    with open("gateway_settings.json") as f:
        return json.load(f)
        
def read_float32_ieee754(registers):
    """2 adet 16 bit registerdan IEEE754 float çevir"""
    combined = (registers[0] << 16) | registers[1]
    return struct.unpack('>f', combined.to_bytes(4, byteorder='big'))[0]

def read_sensors():
    client = ModbusSerialClient(method='rtu', port='/dev/ttyUSB0', baudrate=9600, timeout=1, stopbits=1, bytesize=8, parity='N')
    if not client.connect():
        print("Modbus bağlantısı başarısız!")
        return

    data = []

    # LDR (Slave ID = 1, Register 0x0000, 2 reg)
    try:
        r = client.read_holding_registers(0x0000, 2, slave=1)
        if r.isError():
            raise Exception("LDR read error")
        lux = (r.registers[0] << 16) | r.registers[1]
        data.append({ "name": "LDR", "value": lux, "unit": "Lux" })
    except Exception as e:
        print("LDR:", e)

    # Çevre Sensörü (Slave ID = 123, örnek: CO₂ 0x0008, Sıcaklık 0x000E, Nem 0x0010)
    try:
        co2_regs = client.read_holding_registers(0x0008, 2, slave=123)
        temp_regs = client.read_holding_registers(0x000E, 2, slave=123)
        hum_regs = client.read_holding_registers(0x0010, 2, slave=123)
        if co2_regs.isError() or temp_regs.isError() or hum_regs.isError():
            raise Exception("EnvSensor read error")

        co2 = read_float32_ieee754(co2_regs.registers)
        temp = read_float32_ieee754(temp_regs.registers)
        hum = read_float32_ieee754(hum_regs.registers)

        data.append({ "name": "CO₂", "value": round(co2, 1), "unit": "ppm" })
        data.append({ "name": "Sıcaklık", "value": round(temp, 1), "unit": "°C" })
        data.append({ "name": "Nem", "value": round(hum, 1), "unit": "%" })
    except Exception as e:
        print("Çevre sensörü:", e)

    # PIR (Slave ID = 2, Register = 0x0006)
    try:
        pir = client.read_holding_registers(0x0006, 1, slave=2)
        if pir.isError():
            raise Exception("PIR read error")
        value = pir.registers[0]
        data.append({ "name": "PIR Hareket", "value": "Var" if value == 1 else "Yok", "unit": "" })
    except Exception as e:
        print("PIR:", e)

    # MPPT (Slave ID = 1, örnek 0x3000 PV Voltajı, 0x3001 PV Akımı)
    try:
        pv_volt = client.read_input_registers(0x3000, 1, slave=1)
        pv_curr = client.read_input_registers(0x3001, 1, slave=1)
        if pv_volt.isError() or pv_curr.isError():
            raise Exception("MPPT read error")

        data.append({ "name": "PV Voltajı", "value": pv_volt.registers[0] / 100.0, "unit": "V" })
        data.append({ "name": "PV Akımı", "value": pv_curr.registers[0] / 100.0, "unit": "A" })
    except Exception as e:
        print("MPPT:", e)

    client.close()

    with open(SENSOR_FILE, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == '__main__':
    while True:
        read_sensors()
        time.sleep(10)
