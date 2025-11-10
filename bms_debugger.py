#!/usr/bin/env python3
"""
BMS Debug Tool - Detailed BMS communication testing
"""
import serial
import time
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BMSDebugger:
    def __init__(self, port='/dev/ttyAMA0', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
    
    def connect(self):
        """Open serial connection"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0
            )
            logger.info(f"✅ Connected to {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to open serial port: {e}")
            return False
    
    def send_bms_command(self, command=0x00, read_write=0x01):
        """
        Send BMS command and receive response
        
        Args:
            command: Command address (0x00 = Real-time info, 0x01 = Cell info, etc.)
            read_write: 0x01 = Read, 0x02 = Write
        """
        try:
            # Build frame
            frame = [
                0x3D,       # Frame header
                0x01,       # Source (Host)
                0x02,       # Destination (BMS)
                command,    # Command
                read_write, # R/W
                0x00,       # Data length high
                0x00        # Data length low
            ]
            
            # Calculate checksum
            checksum = sum(frame) & 0xFF
            frame.append(checksum)
            
            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Send request
            logger.info(f"📤 Sending BMS command 0x{command:02X}")
            logger.debug(f"TX: {' '.join([f'{b:02X}' for b in frame])}")
            self.serial.write(bytes(frame))
            
            # Wait for response
            time.sleep(0.3)
            
            # Read response
            response = list(self.serial.read(300))
            
            if not response:
                logger.warning("❌ No response from BMS")
                return None
            
            logger.info(f"📥 Received {len(response)} bytes from BMS")
            logger.debug(f"RX: {' '.join([f'{b:02X}' for b in response[:50]])}{'...' if len(response) > 50 else ''}")
            
            # Validate frame
            if response[0] != 0x3D:
                logger.error(f"❌ Invalid frame header: 0x{response[0]:02X}")
                return None
            
            # Parse header
            src = response[1]
            dst = response[2]
            cmd = response[3]
            rw = response[4]
            data_len = (response[5] << 8) | response[6]
            
            logger.info(f"📋 Frame: SRC=0x{src:02X}, DST=0x{dst:02X}, CMD=0x{cmd:02X}, LEN={data_len}")
            
            # Check if we have complete data
            if len(response) < 7 + data_len + 1:
                logger.warning(f"⚠️  Incomplete response. Expected {7 + data_len + 1}, got {len(response)}")
                return response
            
            # Extract payload
            payload = response[7:7+data_len]
            checksum_recv = response[7+data_len]
            
            # Verify checksum
            checksum_calc = sum(response[:7+data_len]) & 0xFF
            if checksum_calc != checksum_recv:
                logger.warning(f"⚠️  Checksum mismatch: calc=0x{checksum_calc:02X}, recv=0x{checksum_recv:02X}")
            else:
                logger.info("✅ Checksum OK")
            
            return payload
            
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def parse_realtime_data(self, payload):
        """Parse real-time data (command 0x00)"""
        if not payload:
            return None
        
        logger.info("\n" + "="*70)
        logger.info("📊 BMS REAL-TIME DATA")
        logger.info("="*70)
        
        data = {}
        idx = 0
        
        try:
            # Cell voltages (24 cells x 2 bytes)
            logger.info("\n🔋 Cell Voltages:")
            cell_voltages = []
            for i in range(24):
                if idx + 2 <= len(payload):
                    voltage = ((payload[idx] << 8) | payload[idx+1]) * 0.001  # mV to V
                    cell_voltages.append(voltage)
                    if voltage > 0.1:  # Only show connected cells
                        logger.info(f"  Cell {i+1:2d}: {voltage:.3f}V")
                    idx += 2
            
            # Total voltage
            if idx + 2 <= len(payload):
                total_voltage = ((payload[idx] << 8) | payload[idx+1]) * 0.01  # 10mV to V
                data['voltage'] = round(total_voltage, 2)
                logger.info(f"\n⚡ Total Voltage: {total_voltage:.2f}V")
                idx += 2
            
            # Total current
            if idx + 2 <= len(payload):
                raw_current = (payload[idx] << 8) | payload[idx+1]
                if raw_current > 0x7FFF:
                    raw_current = raw_current - 0x10000
                current = raw_current * 0.01  # 10mA to A
                data['current'] = round(current, 2)
                logger.info(f"⚡ Total Current: {current:.2f}A")
                idx += 2
            
            # Calculate power
            if 'voltage' in data and 'current' in data:
                power = data['voltage'] * data['current']
                data['power'] = round(power, 2)
                logger.info(f"⚡ Power: {power:.2f}W")
            
            # Temperatures (3 sensors)
            if idx + 6 <= len(payload):
                logger.info(f"\n🌡️  Temperatures:")
                for i in range(3):
                    temp = ((payload[idx] << 8) | payload[idx+1]) * 0.1
                    logger.info(f"  Sensor {i+1}: {temp:.1f}°C")
                    if i == 0:
                        data['temperature'] = round(temp, 1)
                    idx += 2
            
            # SOC (State of Charge)
            if idx + 1 <= len(payload):
                soc = payload[idx]
                data['soc'] = soc
                logger.info(f"\n🔋 State of Charge (SOC): {soc}%")
                idx += 1
            
            # SOH (State of Health)
            if idx + 1 <= len(payload):
                soh = payload[idx]
                data['soh'] = soh
                logger.info(f"🔋 State of Health (SOH): {soh}%")
                idx += 1
            
            # Remaining capacity
            if idx + 4 <= len(payload):
                remaining_cap = ((payload[idx] << 24) | (payload[idx+1] << 16) | 
                               (payload[idx+2] << 8) | payload[idx+3])
                data['remaining_capacity'] = remaining_cap
                logger.info(f"\n📊 Remaining Capacity: {remaining_cap} mAh ({remaining_cap/1000:.2f} Ah)")
                idx += 4
            
            # Maximum capacity
            if idx + 4 <= len(payload):
                max_cap = ((payload[idx] << 24) | (payload[idx+1] << 16) | 
                          (payload[idx+2] << 8) | payload[idx+3])
                data['max_capacity'] = max_cap
                logger.info(f"📊 Maximum Capacity: {max_cap} mAh ({max_cap/1000:.2f} Ah)")
                idx += 4
            
            # Charge/Discharge cycles
            if idx + 2 <= len(payload):
                cycles = (payload[idx] << 8) | payload[idx+1]
                data['cycles'] = cycles
                logger.info(f"🔄 Charge Cycles: {cycles}")
                idx += 2
            
            logger.info("="*70 + "\n")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error parsing data: {e}")
            import t= debugger.parse_realtime_data(payload)
            if data:
                logger.info("✅ BMS communication successful!")
                logger.info(f"\n📊 Summary:")
                for key, value in data.items():
                    logger.info(f"  {key}: {value}")
            else:
                logger.warning("⚠️  Could not parse BMS data")
        else:
            logger.error("❌ No response from BMS")
            logger.info("\n💡 Troubleshooting tips:")
            logger.info("  1. Check BMS power supply")
            logger.info("  2. Verify RS485 connections (A+ and B-)")
            logger.info("  3. Confirm BMS address is 0x02")
            logger.info("  4. Try different baud rates (9600, 19200)")
            logger.info("  5. Check if another process is using the serial port")
        
        # Optionally test all commands
        response = input("\n\n🔍 Test all BMS commands? (y/n): ")
        if response.lower() == 'y':
            debugger.test_all_commands()
            
    except KeyboardInterrupt:
        logger.info("\n\n⏹️  Stopped by user")
    finally:
        debugger.disconnect()

if __name__ == '__main__':
    main()