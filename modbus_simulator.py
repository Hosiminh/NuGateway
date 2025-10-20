import asyncio
import random
import struct
import logging
from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.datastore.store import ModbusSequentialDataBlock
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server.async_io import StartAsyncSerialServer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def float_to_regs(value):
    """Convert float to two 16-bit registers (IEEE 754)"""
    return struct.unpack('>HH', struct.pack('>f', value))

def generate_env_data():
    """Generate environmental sensor data for slave 123"""
    co2 = float_to_regs(random.uniform(400.0, 1500.0))
    temp = float_to_regs(random.uniform(5.0, 35.0))
    hum = float_to_regs(random.uniform(30.0, 90.0))
    pm25 = float_to_regs(random.uniform(5.0, 80.0))
    pm10 = float_to_regs(random.uniform(10.0, 150.0))
    lux = float_to_regs(random.uniform(1000, 50000))
    
    # Address mapping for environmental sensor:
    # 0x0008 (8-9): CO2
    # 0x000A (10-11): PM2.5
    # 0x000C (12-13): PM10
    # 0x000E (14-15): Temperature
    # 0x0010 (16-17): Humidity
    # 0x0012 (18-19): Illumination
    
    data = [0] * 20  # Initialize with zeros
    data[8:10] = co2
    data[10:12] = pm25
    data[12:14] = pm10
    data[14:16] = temp
    data[16:18] = hum
    data[18:20] = lux
    
    return data

def generate_ldr_data():
    """Generate LDR sensor data for slave 1"""
    # LDR returns 32-bit lux value in registers 0-1
    lux = random.randint(5000, 45000)
    return [(lux >> 16) & 0xFFFF, lux & 0xFFFF]

def generate_pir_data():
    """Generate PIR sensor data for slave 2"""
    # PIR returns 0 or 1 at register 6
    data = [0] * 7
    data[6] = random.choice([0, 1])
    return data

def generate_mppt_data():
    """Generate MPPT charge controller data for slave 3"""
    # MPPT uses input registers
    # Address 0x3000: PV Voltage (in 0.01V)
    # Address 0x3001: PV Current (in 0.01A)
    
    voltage = int(random.uniform(15.0, 20.0) * 100)  # 1500-2000 (15.00-20.00V)
    current = int(random.uniform(2.0, 8.0) * 100)     # 200-800 (2.00-8.00A)
    
    # Create data starting from address 0
    # We need to fill up to 0x3001
    data = [0] * 0x3002
    data[0x3000] = voltage
    data[0x3001] = current
    
    return data

def generate_bms_data():
    """Generate BMS (Battery Management System) data for slave 4"""
    # BMS uses input registers
    # 0x3004: Battery Voltage (in 0.01V)
    # 0x3005: Battery Current (in 0.01A)
    # 0x3020: SOC (State of Charge %)
    # 0x3021: SOH (State of Health %)
    # 0x3022: Battery Temperature (in 0.1°C)
    # 0x3023: Discharge time (minutes)
    # 0x3024: Charge time (minutes)
    
    voltage = int(random.uniform(11.5, 13.0) * 100)   # 1150-1300 (11.50-13.00V)
    current = int(random.uniform(0.5, 5.0) * 100)      # 50-500 (0.50-5.00A)
    soc = random.randint(10, 100)                      # 10-100%
    soh = random.randint(80, 100)                      # 80-100%
    temp = int(random.uniform(20.0, 45.0) * 10)       # 200-450 (20.0-45.0°C)
    discharge = random.randint(30, 180)                # 30-180 min
    charge = random.randint(15, 120)                   # 15-120 min
    
    # Create data array up to 0x3024
    data = [0] * 0x3025
    data[0x3004] = voltage
    data[0x3005] = current
    data[0x3020] = soc
    data[0x3021] = soh
    data[0x3022] = temp
    data[0x3023] = discharge
    data[0x3024] = charge
    
    return data

# Initialize data stores for each slave
store = {
    1: ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, generate_ldr_data())
    ),
    2: ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, generate_pir_data())
    ),
    3: ModbusSlaveContext(
        ir=ModbusSequentialDataBlock(0, generate_mppt_data())
    ),
    4: ModbusSlaveContext(
        ir=ModbusSequentialDataBlock(0, generate_bms_data())
    ),
    123: ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, generate_env_data())
    )
}

context = ModbusServerContext(slaves=store, single=False)

# Device identification
identity = ModbusDeviceIdentification()
identity.VendorName = "nuGateway"
identity.ProductCode = "NGW"
identity.VendorUrl = "https://nuteknoloji.com"
identity.ProductName = "Modbus Sensor Simulator"
identity.ModelName = "Sim01"
identity.MajorMinorRevision = "2.0"

async def update_loop():
    """Continuously update sensor data every 5 seconds"""
    while True:
        try:
            store[1].setValues(3, 0, generate_ldr_data())
            store[2].setValues(3, 0, generate_pir_data())
            store[3].setValues(4, 0, generate_mppt_data())
            store[4].setValues(4, 0, generate_bms_data())
            store[123].setValues(3, 0, generate_env_data())
            logger.debug("Sensor data updated")
        except Exception as e:
            logger.error(f"Error updating sensor data: {e}")
        
        await asyncio.sleep(5)

async def run():
    """Start the Modbus RTU simulator server"""
    logger.info("🚀 Modbus RTU Simulator başlatılıyor (/tmp/ttySIM0)...")
    
    # Start data update loop
    asyncio.create_task(update_loop())
    
    # Start Modbus server
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
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user")
    except Exception as e:
        logger.error(f"Simulator error: {e}")