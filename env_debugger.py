#!/usr/bin/env python3
"""
Environmental Sensor Debug Tool
"""
import serial
import time
import logging
import struct
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ENVDebugger:
    def __init__(self, port='/dev/ttyAMA0', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.slave_id = 0x7B  # ENV sensor slave ID
    
    def connect(self):
        """Open serial connection"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            logger.info(f"✅ Connected to {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to open serial port: {e}")
            return False
    
    @staticmethod
    def calculate_crc(data):
        """Calculate Modbus CRC-16"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return [crc & 0xFF, (crc >> 8) & 0xFF]
    
    @staticmethod
    def bytes_to_float_ieee754(b1, b2, b3, b4):
        """Convert 4 bytes to IEEE 754 float"""
        try:
            packed = struct.pack('>BBBB', b1, b2, b3, b4)
            value = struct.unpack('>f', packed)[0]
            return value
        except:
            return 0.0
    
    def read_registers(self, address, count):
        """Read registers from ENV sensor"""
        try:
            # Build request (Function code 0x03 = Read Holding Registers)
            request = [
                self.slave_id,
                0x03,  # Function code
                (address >> 8) & 0xFF,
                address & 0xFF,
                (count >> 8) & 0xFF,
                count & 0xFF
            ]
            
            # Add CRC
            crc = self.calculate_crc(request)
            request.extend(crc)
            
            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Send request
            logger.debug(f"📤 TX: {' '.join([f'{b:02X}' for b in request])}")
            self.serial.write(bytes(request))
            
            # Wait for response
            time.sleep(0.1)
            
            # Read response
            expected_length = 3 + (count * 2) + 2
            response = list(self.serial.read(expected_length))
            
            if not response:
                logger.warning("❌ No response")
                return None
            
            logger.debug(f"📥 RX: {' '.join([f'{b:02X}' for b in response])}")
            
            # Check for exception
            if len(response) >= 2 and (response[1] & 0x80):
                exception_code = response[2] if len(response) > 2 else 0
                logger.error(f"❌ Modbus exception: 0x{exception_code:02X}")
                return None
            
            # Verify CRC
            received_crc = response[-2:]
            calculated_crc = self.calculate_crc(response[:-2])
            if received_crc != calculated_crc:
                logger.error("❌ CRC error")
                return None
            
            # Extract data
            byte_count = response[2]
            data_bytes = response[3:3+byte_count]
            
            # Convert to 16-bit registers
            registers = []
            for i in range(0, len(data_bytes), 2):
                if i + 1 < len(data_bytes):
                    value = (data_bytes[i] << 8) | data_bytes[i + 1]
                    registers.append(value)
            
            return registers
            
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return None
    
    def test_register(self, name, address, count=2):
        """Test reading a specific register"""
        logger.info(f"\n📊 Testing {name} (Address: 0x{address:04X}, Count: {count})")
        logger.info("-" * 60)
        
        registers = self.read_registers(address, count)
        
        if not registers:
            logger.warning(f"⚠️  Failed to read {name}")
            return None
        
        logger.info(f"✅ Raw registers: {[f'0x{r:04X}' for r in registers]}")
        
        # If 2 registers (IEEE 754 float)
        if len(registers) >= 2:
            b1 = (registers[0] >> 8) & 0xFF
            b2 = registers[0] & 0xFF
            b3 = (registers[1] >> 8) & 0xFF
            b4 = registers[1] & 0xFF
            
            value = self.bytes_to_float_ieee754(b1, b2, b3, b4)
            logger.info(f"✅ Decoded value: {value:.2f}")
            return value
        
        return registers[0] if registers else None
    
    def scan_all_registers(self):
        """Scan all documented ENV registers"""
        print("\n" + "="*70)
        print("🔍 SCANNING ALL ENV SENSOR REGISTERS")
        print("="*70)
        
        registers_to_test = {
            "CO2": 0x0020,
            "PM2.5": 0x0022,
            "Temperature": 0x0024,
            "Humidity": 0x0026,
            "PM10": 0x0028,  # Trying alternative address
            "Illumination": 0x0012,
            "Noise": 0x0014,
            "Atmospheric Pressure": 0x0016,
        }
        
        results = {}
        for name, addr in registers_to_test.items():
            value = self.test_register(name, addr)
            if value is not None:
                results[name] = value
            time.sleep(0.2)
        
        print("\n" + "="*70)
        print("📋 SUMMARY OF READINGS")
        print("="*70)
        
        if results:
            for name, value in results.items():
                print(f"  {name:20s}: {value:.2f}")
        else:
            print("  ❌ No valid readings obtained")
        
        return results
    
    def continuous_monitoring(self, interval=5):
        """Continuously monitor ENV sensor"""
        print("\n" + "="*70)
        print("🔄 CONTINUOUS MONITORING (Press Ctrl+C to stop)")
        print("="*70)
        
        try:
            while True:
                # Read key parameters
                temp = self.test_register("Temperature", 0x0024)
                time.sleep(0.2)
                
                humidity = self.test_register("Humidity", 0x0026)
                time.sleep(0.2)
                
                co2 = self.test_register("CO2", 0x0020)
                time.sleep(0.2)
                
                pm25 = self.test_register("PM2.5", 0x0022)
                
                print(f"\n⏱
    
    if not debugger.connect():
        logger.error("Failed to connect. Exiting.")
        return
    
    try:
        while True:
            print("\n" + "="*70)
            print("OPTIONS:")
            print("="*70)
            print("  1. Scan all registers")
            print("  2. Continuous monitoring")
            print("  3. Test specific register")
            print("  4. Exit")
            print("="*70)
            
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == '1':
                debugger.scan_all_registers()
            elif choice == '2':
                debugger.continuous_monitoring()
            elif choice == '3':
                addr_input = input("Enter register address (hex, e.g., 0x0024): ").strip()
                try:
                    addr = int(addr_input, 16)
                    name = input("Enter register name: ").strip()
                    debugger.test_register(name, addr)
                except ValueError:
                    print("❌ Invalid address format")
            elif choice == '4':
                break
            else:
                print("❌ Invalid option")
                
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    finally:
        debugger.disconnect()

if __name__ == '__main__':
    main()