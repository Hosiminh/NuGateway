#!/usr/bin/env python3
"""
Raw Modbus Packet Test
Test MPPT with different CRC byte orders
"""
import serial
import time
import struct
import logging

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RawModbusTest:
    """Raw Modbus packet tester with CRC variations"""
    
    def __init__(self, port='/dev/ttyAMA0', baudrate=9600, direction_pin=8):
        self.port = port
        self.baudrate = baudrate
        self.direction_pin = direction_pin
        self.gpio_enabled = False
        
        # Setup GPIO
        if GPIO_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.direction_pin, GPIO.OUT)
                GPIO.output(self.direction_pin, GPIO.LOW)
                self.gpio_enabled = True
                logger.info("✅ GPIO initialized")
            except Exception as e:
                logger.warning(f"GPIO setup failed: {e}")
        
        # Open serial port
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=2
        )
        logger.info(f"✅ Serial port {port} opened")
    
    def _set_tx_mode(self):
        if self.gpio_enabled:
            GPIO.output(self.direction_pin, GPIO.HIGH)
            time.sleep(0.001)
    
    def _set_rx_mode(self):
        if self.gpio_enabled:
            time.sleep(0.001)
            GPIO.output(self.direction_pin, GPIO.LOW)
    
    def crc16_modbus(self, data):
        """Calculate CRC-16/MODBUS (standard)"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def send_and_receive(self, request_packet, description=""):
        """Send packet and receive response"""
        print(f"\n{'='*70}")
        print(f"📤 {description}")
        print(f"{'='*70}")
        print(f"TX: {' '.join(f'{b:02X}' for b in request_packet)}")
        
        # Clear buffer
        self.ser.reset_input_buffer()
        
        # Send
        self._set_tx_mode()
        self.ser.write(bytes(request_packet))
        self.ser.flush()
        self._set_rx_mode()
        
        # Receive
        time.sleep(0.1)
        response = self.ser.read(100)
        
        if response:
            print(f"RX: {' '.join(f'{b:02X}' for b in response)} ({len(response)} bytes)")
            return response
        else:
            print("RX: (no response)")
            return None
    
    def test_mppt_slave(self, slave_id):
        """Test MPPT at different addresses with different CRC methods"""
        
        print(f"\n{'='*70}")
        print(f"🔬 TESTING MPPT - Slave 0x{slave_id:02X} ({slave_id})")
        print(f"{'='*70}")
        
        # Test 1: Standard MPPT registers (0x3000-0x3001) with STANDARD CRC
        print("\n" + "="*70)
        print("TEST 1: Standard CRC (LSB First) - Address 0x3000")
        print("="*70)
        
        # Build request: Read Input Registers (FC=04), Address=0x3000, Count=2
        request = [slave_id, 0x04, 0x30, 0x00, 0x00, 0x02]
        crc = self.crc16_modbus(request)
        request.append(crc & 0xFF)         # CRC Low byte first (LSB)
        request.append((crc >> 8) & 0xFF)  # CRC High byte
        
        response = self.send_and_receive(request, "MPPT 0x3000 - Standard CRC (LSB First)")
        
        if response and len(response) > 2:
            print("✅ Got response!")
            self.parse_mppt_response(response)
            return True
        
        # Test 2: REVERSED CRC (MSB First)
        print("\n" + "="*70)
        print("TEST 2: Reversed CRC (MSB First) - Address 0x3000")
        print("="*70)
        
        request = [slave_id, 0x04, 0x30, 0x00, 0x00, 0x02]
        crc = self.crc16_modbus(request)
        request.append((crc >> 8) & 0xFF)  # CRC High byte first (MSB)
        request.append(crc & 0xFF)         # CRC Low byte
        
        response = self.send_and_receive(request, "MPPT 0x3000 - Reversed CRC (MSB First)")
        
        if response and len(response) > 2:
            print("✅ Got response!")
            self.parse_mppt_response(response)
            return True
        
        # Test 3: Different address (0x9020 from your example)
        print("\n" + "="*70)
        print("TEST 3: Address 0x9020 - Standard CRC")
        print("="*70)
        
        request = [slave_id, 0x03, 0x90, 0x20, 0x00, 0x02]
        crc = self.crc16_modbus(request)
        request.append(crc & 0xFF)
        request.append((crc >> 8) & 0xFF)
        
        response = self.send_and_receive(request, "MPPT 0x9020 - Standard CRC")
        
        if response and len(response) > 2:
            print("✅ Got response!")
            return True
        
        # Test 4: Try Holding Registers instead of Input Registers
        print("\n" + "="*70)
        print("TEST 4: Holding Registers (FC=03) - Address 0x3000")
        print("="*70)
        
        request = [slave_id, 0x03, 0x30, 0x00, 0x00, 0x02]
        crc = self.crc16_modbus(request)
        request.append(crc & 0xFF)
        request.append((crc >> 8) & 0xFF)
        
        response = self.send_and_receive(request, "MPPT 0x3000 - Holding Registers")
        
        if response and len(response) > 2:
            print("✅ Got response!")
            self.parse_mppt_response(response)
            return True
        
        # Test 5: Address 0x0000
        print("\n" + "="*70)
        print("TEST 5: Address 0x0000 - Standard CRC")
        print("="*70)
        
        request = [slave_id, 0x04, 0x00, 0x00, 0x00, 0x02]
        crc = self.crc16_modbus(request)
        request.append(crc & 0xFF)
        request.append((crc >> 8) & 0xFF)
        
        response = self.send_and_receive(request, "MPPT 0x0000")
        
        if response and len(response) > 2:
            print("✅ Got response!")
            self.parse_mppt_response(response)
            return True
        
        print("\n❌ No valid response from any test")
        return False
    
    def parse_mppt_response(self, response):
        """Parse MPPT response"""
        if len(response) < 7:
            print("  ⚠️ Response too short")
            return
        
        try:
            slave_id = response[0]
            func_code = response[1]
            byte_count = response[2]
            
            print(f"  📊 Slave ID: 0x{slave_id:02X}")
            print(f"  📊 Function: 0x{func_code:02X}")
            print(f"  📊 Bytes: {byte_count}")
            
            if byte_count >= 4:
                reg1 = (response[3] << 8) | response[4]
                reg2 = (response[5] << 8) | response[6]
                
                print(f"  📊 Register 1: {reg1} (0x{reg1:04X})")
                print(f"  📊 Register 2: {reg2} (0x{reg2:04X})")
                
                # Try as voltage/current
                voltage = reg1 / 100.0
                current = reg2 / 100.0
                print(f"  🔋 Possible Voltage: {voltage}V")
                print(f"  ⚡ Possible Current: {current}A")
                print(f"  💡 Possible Power: {voltage * current}W")
        except Exception as e:
            print(f"  ❌ Parse error: {e}")
    
    def close(self):
        """Cleanup"""
        self.ser.close()
        if self.gpio_enabled:
            GPIO.cleanup(self.direction_pin)

if __name__ == "__main__":
    print("\n" + "🔬 Raw Modbus CRC Test Tool")
    print("="*70)
    
    tester = RawModbusTest(port='/dev/ttyAMA0', baudrate=9600, direction_pin=8)
    
    # Test slave 0xC8 (200)
    print("\nTesting Slave 0xC8 (200) - Possible MPPT")
    tester.test_mppt_slave(0xC8)
    
    # Also test 0x0A (10) from your example
    print("\n\nTesting Slave 0x0A (10) - From your packet example")
    tester.test_mppt_slave(0x0A)
    
    # Test 0x01 (original MPPT address)
    print("\n\nTesting Slave 0x01 (1) - Original MPPT address")
    tester.test_mppt_slave(0x01)
    
    tester.close()
    
    print("\n" + "="*70)
    print("🎯 Test complete!")
    print("="*70)