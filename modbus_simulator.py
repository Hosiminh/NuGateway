import asyncio
import random
import struct
from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.datastore.store import ModbusSequentialDataBlock
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server.async_io import StartAsyncSerialServer

# Dummy veri üreticileri
def float_to_regs(value):
    return struct.unpack('>HH', struct.pack('>f', value))

def generate_env_data():
    co2 = float_to_regs(random.uniform(400.0, 1500.0))
    temp = float_to_regs(random.uniform(5.0, 35.0))
    hum = float_to_regs(random.uniform(30.0, 90.0))
    pm25 = float_to_regs(random.uniform(5.0, 80.0))
    pm10 = float_to_regs(random.uniform(10.0, 150.0))
    lux = float_to_regs(random.uniform(1000, 50000))
    data = [0]*8 + list(co2) + [0]*2 + list(temp) + list(hum) + list(pm25) + list(pm10) + list(lux)
    return data

def generate_ldr_data():
    lux = random.randint(5000, 45000)
    return [(lux >> 16) & 0xFFFF, lux & 0xFFFF]

def generate_pir_data():
    return [random.choice([0, 1])]

def generate_mppt_data():
    voltage = int(random.uniform(15.0, 20.0) * 100)
    current = int(random.uniform(2.0, 8.0) * 100)
    return [0]*0x3000 + [voltage, current]

def generate_bms_data():
    voltage = int(random.uniform(11.5, 13.0) * 100)
    current = int(random.uniform(0.5, 5.0) * 100)
    soc = random.randint(10, 100)
    soh = random.randint(80, 100)
    temp = int(random.uniform(20.0, 45.0) * 10)
    discharge = random.randint(30, 180)
    charge = random.randint(15, 120)
    data = [0]*0x3020
    data += [soc, soh, temp, discharge, charge]
    return [voltage, current] + data

# Her slave için ayrı veri bloğu
store = {
    1: ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, generate_ldr_data())),
    2: ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, generate_pir_data())),
    3: ModbusSlaveContext(ir=ModbusSequentialDataBlock(0, generate_mppt_data())),
    4: ModbusSlaveContext(ir=ModbusSequentialDataBlock(0, generate_bms_data())),
    123: ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, generate_env_data()))
}

context = ModbusServerContext(slaves=store, single=False)

identity = ModbusDeviceIdentification()
identity.VendorName = "nuGateway"
identity.ProductCode = "NGW"
identity.VendorUrl = "https://nuteknoloji.com"
identity.ProductName = "Modbus Sensor Simulator"
identity.ModelName = "Sim01"
identity.MajorMinorRevision = "1.0"

async def update_loop():
    while True:
        store[1].setValues(3, 0, generate_ldr_data())
        store[2].setValues(3, 0, generate_pir_data())
        store[3].setValues(4, 0, generate_mppt_data())
        store[4].setValues(4, 0, generate_bms_data())
        store[123].setValues(3, 0, generate_env_data())
        await asyncio.sleep(5)

async def run():
    print("🚀 Modbus RTU Simülatörü başlatılıyor (/tmp/ttySIM0)...")
    asyncio.create_task(update_loop())
    await StartAsyncSerialServer(
        context=context,
        identity=identity,
        port="/tmp/ttySIM0",
        baudrate=9600,
        stopbits=1,
        bytesize=8,
        parity='N',
        timeout=1
    )

if __name__ == "__main__":
    asyncio.run(run())
