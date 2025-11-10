#!/usr/bin/env python3
"""
Modbus RTU Simulator - FIXED VERSION
Server in main thread, updates in background
"""
import random
import struct
import logging
import time
from threading import Thread

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import pymodbus 2.5.3
try:
    from pymodbus.server.sync import StartSerialServer
    from pymodbus.datastore import ModbusSequentialDataBlock
    from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
    from pymodbus.device import ModbusDeviceIdentification
    logger.info("✅ Pymodbus 2.5.3 imported")
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    exit(1)

def float_to_regs(value):
    """Convert float to two registers"""
    return struct.unpack('>HH', struct.pack('>f', value))

# Global store reference
store_dict = {}

def generate_and_update_data():
    """Generate and update sensor data WITH CORRECT ADDRESS MAPPING"""
    global store_dict
    
    try:
        # Slave 1 (LDR) - Update address 0x0000
        lux = random.randint(10000, 40000)
        ldr_data = [(lux >> 16) & 0xFFFF, lux & 0xFFFF]
        if 1 in store_dict:
            store_dict[1].setValues(3, 0, ldr_data)  # Write to address 0
        
        # Slave 2 (PIR) - Update address 0x0006
        pir_value = random.choice([0, 1])
        pir_data = [0] * 20
        pir_data[6] = pir_value
        if 2 in store_dict:
            store_dict[2].setValues(3, 0, pir_data)  # Write starting from 0
        
        # Slave 123 (Environmental) - Update addresses 0x0008-0x0012
        env_data = [0] * 50
        env_data[8:10] = float_to_regs(random.uniform(400, 1500))    # CO2
        env_data[10:12] = float_to_regs(random.uniform(5, 50))       # PM2.5
        env_data[12:14] = float_to_regs(random.uniform(10, 100))     # PM10
        env_data[14:16] = float_to_regs(random.uniform(18, 28))      # Temp
        env_data[16:18] = float_to_regs(random.uniform(40, 80))      # Humidity
        env_data[18:20] = float_to_regs(random.uniform(5000, 40000)) # Illumination
        if 123 in store_dict:
            store_dict[123].setValues(3, 0, env_data)
        
        # Slave 3 (MPPT) - Update INPUT registers 0x3000-0x3001
        mppt_data = [0] * 0x3010
        mppt_data[0x3000] = int(random.uniform(16, 19) * 100)
        mppt_data[0x3001] = int(random.uniform(3, 7) * 100)
        if 3 in store_dict:
            store_dict[3].setValues(4, 0, mppt_data)  # INPUT registers
        
        # Slave 4 (BMS) - Update INPUT registers 0x3004-0x3024
        bms_data = [0] * 0x3030
        bms_data[0x3004] = int(random.uniform(12, 12.8) * 100)
        bms_data[0x3005] = int(random.uniform(1, 4) * 100)
        bms_data[0x3020] = random.randint(40, 95)
        bms_data[0x3021] = random.randint(85, 100)
        bms_data[0x3022] = int(random.uniform(22, 35) * 10)
        bms_data[0x3023] = random.randint(60, 150)
        bms_data[0x3024] = random.randint(30, 90)
        if 4 in store_dict:
            store_dict[4].setValues(4, 0, bms_data)  # INPUT registers
        
        return True
    except Exception as e:
        logger.error(f"Update error: {e}")
        return False

def update_loop():
    """Background thread for data updates"""
    logger.info("Data update thread started")
    time.sleep(3)  # Wait for server to initialize
    
    counter = 0
    while True:
        try:
            counter += 1
            if generate_and_update_data():
                logger.info(f"✅ Update #{counter}: Data refreshed")
            else:
                logger.warning(f"⚠️ Update #{counter}: Failed")
        except Exception as e:
            logger.error(f"Update loop error: {e}")
        
        time.sleep(5)

def run_server():
    """Initialize and run Modbus server"""
    global store_dict
    
    logger.info("=" * 70)
    logger.info("🚀 MODBUS RTU SIMULATOR - FIXED VERSION")
    logger.info("=" * 70)
    logger.info("Port: /tmp/ttySIM0")
    logger.info("Baudrate: 9600, 8N1")
    logger.info("Slaves: 1, 2, 3, 4, 123")
    logger.info("=" * 70)
    
    # Initialize stores with CORRECT ADDRESS MAPPING
    logger.info("Initializing data stores with address mapping...")
    
    # Slave 1 (LDR) - Reader queries address 0x0000
    ldr_block = [0] * 100
    ldr_block[0] = 0      # High word of lux
    ldr_block[1] = 30000  # Low word of lux
    store_dict[1] = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, ldr_block),
        ir=ModbusSequentialDataBlock(0, [0]*100)
    )
    
    # Slave 2 (PIR) - Reader queries address 0x0006
    pir_block = [0] * 20
    pir_block[6] = 1  # Motion at address 6
    store_dict[2] = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, pir_block),
        ir=ModbusSequentialDataBlock(0, [0]*100)
    )
    
    # Slave 3 (MPPT) - Reader queries INPUT registers 0x3000, 0x3001
    mppt_block = [0] * 0x3010
    mppt_block[0x3000] = 1800  # Voltage at 0x3000
    mppt_block[0x3001] = 500   # Current at 0x3001
    store_dict[3] = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, [0]*100),
        ir=ModbusSequentialDataBlock(0, mppt_block)
    )
    
    # Slave 4 (BMS) - Reader queries INPUT registers 0x3004-0x3024
    bms_block = [0] * 0x3030
    bms_block[0x3004] = 1250  # Voltage at 0x3004
    bms_block[0x3005] = 250   # Current at 0x3005
    bms_block[0x3020] = 85    # SOC at 0x3020
    bms_block[0x3021] = 95    # SOH at 0x3021
    bms_block[0x3022] = 280   # Temp at 0x3022
    bms_block[0x3023] = 120   # Discharge time at 0x3023
    bms_block[0x3024] = 60    # Charge time at 0x3024
    store_dict[4] = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, [0]*100),
        ir=ModbusSequentialDataBlock(0, bms_block)
    )
    
    # Slave 123 (Environmental) - Reader queries addresses 0x0008-0x0012
    env_block = [0] * 50
    # CO2 at 0x0008-0x0009
    env_block[8:10] = float_to_regs(800.0)
    # PM2.5 at 0x000A-0x000B
    env_block[10:12] = float_to_regs(15.0)
    # PM10 at 0x000C-0x000D
    env_block[12:14] = float_to_regs(25.0)
    # Temp at 0x000E-0x000F
    env_block[14:16] = float_to_regs(23.5)
    # Humidity at 0x0010-0x0011
    env_block[16:18] = float_to_regs(60.0)
    # Illumination at 0x0012-0x0013
    env_block[18:20] = float_to_regs(25000.0)
    store_dict[123] = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*100),
        co=ModbusSequentialDataBlock(0, [0]*100),
        hr=ModbusSequentialDataBlock(0, env_block),
        ir=ModbusSequentialDataBlock(0, [0]*100)
    )
    
    context = ModbusServerContext(slaves=store_dict, single=False)
    
    identity = ModbusDeviceIdentification()
    identity.VendorName = "nuGateway"
    identity.ProductCode = "NGW-FIXED"
    identity.ProductName = "Modbus RTU Simulator (Fixed)"
    identity.ModelName = "Fixed-01"
    identity.MajorMinorRevision = "2.5.3"
    
    logger.info("✅ Data stores initialized")
    
    # Start update thread BEFORE server
    update_thread = Thread(target=update_loop, daemon=True)
    update_thread.start()
    logger.info("✅ Update thread started")
    
    # Start server (BLOCKING)
    logger.info("Starting Modbus server (blocking)...")
    logger.info("Server is ready to accept connections!")
    
    try:
        StartSerialServer(
            context,
            identity=identity,
            port='/tmp/ttySIM0',
            timeout=1,
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1
        )
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        run_server()
    except KeyboardInterrupt:
        logger.info("\n✋ Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")