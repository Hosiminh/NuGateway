#!/usr/bin/env python3
"""
NuGateway Modbus Reader - Complete Implementation with Excellent BMS Reading
Combines best BMS code from old version with working MPPT/ENV/LDR code
"""
from config import config_manager
USE_SIM = config_manager.get("use_simulator", False)

import serial
import time
import logging
import struct
import json
from typing import Optional, Dict, List
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModbusReader:
    """Modbus RTU reader for multiple devices"""
    
    def __init__(self, port: str = '/dev/ttyAMA0', baudrate: int = 9600, 
                 timeout: float = 1.0):
        """
        Initialize Modbus reader
        
        Args:
            port: Serial port path
            baudrate: Communication speed
            timeout: Read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        
    def connect(self) -> bool:
        """Open serial connection"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            logger.info(f"✅ Connected to {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to open serial port: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("🔌 Serial port closed")
    
    @staticmethod
    def calculate_crc(data: List[int]) -> List[int]:
        """Calculate Modbus CRC-16 (Little-Endian)"""
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
    def verify_crc(data: List[int]) -> bool:
        """Verify CRC of received data"""
        if len(data) < 3:
            return False
        
        received_crc = data[-2:]
        calculated_crc = ModbusReader.calculate_crc(data[:-2])
        return received_crc == calculated_crc
    
    def read_registers(self, slave_id: int, start_address: int, 
                       count: int, function_code: int = 0x04) -> Optional[List[int]]:
        """Read registers from Modbus device"""
        if not self.serial or not self.serial.is_open:
            logger.error("Serial port not open")
            return None
        
        # Build request
        request = [
            slave_id,
            function_code,
            (start_address >> 8) & 0xFF,
            start_address & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF
        ]
        
        # Add CRC
        crc = self.calculate_crc(request)
        request.extend(crc)
        
        try:
            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Send request
            self.serial.write(bytes(request))
            logger.debug(f"TX: {' '.join([f'{b:02X}' for b in request])}")
            
            # Wait for response
            time.sleep(0.1)
            
            # Calculate expected response length
            expected_length = 3 + (count * 2) + 2
            
            response = list(self.serial.read(expected_length))
            
            if not response:
                logger.warning(f"No response from slave {slave_id:02X}")
                return None
            
            logger.debug(f"RX: {' '.join([f'{b:02X}' for b in response])}")
            
            # Check for exception
            if len(response) >= 2 and (response[1] & 0x80):
                exception_code = response[2] if len(response) > 2 else 0
                logger.error(f"Modbus exception {exception_code:02X} from slave {slave_id:02X}")
                return None
            
            # Verify CRC
            if not self.verify_crc(response):
                logger.error(f"CRC error in response from slave {slave_id:02X}")
                return None
            
            # Check response format
            if len(response) < 5:
                logger.error(f"Response too short from slave {slave_id:02X}")
                return None
            
            # Extract data
            byte_count = response[2]
            data_bytes = response[3:3+byte_count]
            
            # Convert bytes to 16-bit registers
            registers = []
            for i in range(0, len(data_bytes), 2):
                if i + 1 < len(data_bytes):
                    reg_value = (data_bytes[i] << 8) | data_bytes[i+1]
                    registers.append(reg_value)
            
            return registers
            
        except Exception as e:
            logger.error(f"Error reading registers: {e}")
            return None
    
    def read_bms_data(self) -> Optional[Dict]:
        """
        Read BMS data using excellent protocol from old code
        Slave ID: 0x3D
        """
        logger.info("🔋 Reading BMS...")
        
        def bms_send(cmd, rw=0x01, data=b""):
            """Send BMS command with custom protocol"""
            frame = bytes([0x3D, 0x01, 0x02, cmd, rw, 0x00, len(data)]) + data
            chk = (sum(frame) & 0xFF)
            tx = frame + bytes([chk])
            
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.serial.write(tx)
            logger.debug(f"BMS TX: {tx.hex().upper()}")
            
            time.sleep(0.8)
            rx = self.serial.read(self.serial.in_waiting or 255)
            
            # Read in chunks
            for _ in range(3):
                time.sleep(0.2)
                extra = self.serial.read(self.serial.in_waiting or 255)
                if extra:
                    rx += extra
                else:
                    break
            
            if not rx:
                logger.warning(f"BMS: No response (Cmd=0x{cmd:02X})")
                return None
            
            logger.debug(f"BMS RX: {rx.hex().upper()}")
            
            # Verify checksum
            if (sum(rx[:-1]) & 0xFF) != rx[-1]:
                logger.error(f"BMS: Checksum error (Cmd=0x{cmd:02X})")
                return None
            
            return rx
        
        def u16_le(buf, i):
            """Read unsigned 16-bit little-endian"""
            return buf[i] | (buf[i + 1] << 8)
        
        def i16_le(buf, i):
            """Read signed 16-bit little-endian"""
            v = u16_le(buf, i)
            return v - 65536 if v > 32767 else v
        
        try:
            data = {}
            
            # -------- 0x27: Cell count --------
            rx = bms_send(0x27)
            series_count = 4  # Default
            if rx and len(rx) > 6:
                d = rx[6:-1]
                series_count = d[-1] if 1 <= d[-1] <= 24 else 4
                logger.info(f"   ✓ Cell count: {series_count}")
            else:
                logger.warning("   ⚠️ Cell count not read, using default 4")
            
            time.sleep(0.5)
            
            # -------- 0x00: Real-time data --------
            rx = bms_send(0x00)
            if rx and len(rx) > 20:
                d = rx[6:-1][1:]  # Skip first byte
                
                # 1) Cell voltages
                cells = [round(u16_le(d, i * 2) / 1000.0, 3) for i in range(series_count)]
                data['bms_cell_1_voltage'] = cells[0] if len(cells) > 0 else 0.0
                data['bms_cell_2_voltage'] = cells[1] if len(cells) > 1 else 0.0
                data['bms_cell_3_voltage'] = cells[2] if len(cells) > 2 else 0.0
                data['bms_cell_4_voltage'] = cells[3] if len(cells) > 3 else 0.0
                
                for i, v in enumerate(cells, 1):
                    logger.info(f"   ✓ Cell {i}: {v:.3f}V")
                
                # 2) Find pack voltage/current position dynamically
                total_v = sum(cells)
                v_guess = int(round(total_v * 100))
                v_low, v_high = v_guess - 12, v_guess + 12
                
                # Skip long zero padding
                start = max(2 * series_count, 8)
                zero_run = 0
                base_start = start
                for i in range(start, len(d)):
                    if d[i] == 0x00:
                        zero_run += 1
                    else:
                        if zero_run >= 16:
                            base_start = i
                            break
                        zero_run = 0
                
                # Find pack voltage marker
                pack_idx = None
                for i in range(base_start, len(d) - 8):
                    val = u16_le(d, i)
                    if v_low <= val <= v_high:
                        pack_idx = i
                        break
                
                if pack_idx is None:
                    # Use cell sum as fallback
                    vpack = round(total_v, 2)
                    ipack = 0.0
                    soc = 0
                    soh = 0
                    logger.warning(f"   ⚠️ Pack marker not found, using sum: {vpack:.2f}V")
                else:
                    # 3) Pack voltage & current
                    vpack = round(u16_le(d, pack_idx) / 100.0, 2)
                    ipack = round(i16_le(d, pack_idx + 2) / 100.0, 2)
                    
                    # 4) SOC / SOH
                    cand_soc = d[pack_idx + 6] if (pack_idx + 6) < len(d) else 255
                    cand_soh = d[pack_idx + 7] if (pack_idx + 7) < len(d) else 255
                    soc = cand_soc if 0 <= cand_soc <= 100 else 0
                    soh = cand_soh if 0 <= cand_soh <= 100 else 0
                
                data['bms_battery_voltage'] = vpack
                data['bms_battery_current'] = ipack
                data['bms_battery_soc'] = soc
                data['bms_battery_soh'] = soh
                data['bms_battery_power'] = round(vpack * ipack, 2)
                
                logger.info(f"   ✓ Pack: {vpack:.2f}V, {ipack:.2f}A, SOC: {soc}%, SOH: {soh}%")
            else:
                logger.warning("   ⚠️ Real-time data not received")
            
            time.sleep(0.5)
            
            # -------- 0x2D & 0x2E: MOS status --------
            for cmd, label, key in [(0x2D, "Discharge", "bms_discharge_mos_status"), 
                                     (0x2E, "Charge", "bms_charge_mos_status")]:
                rx = bms_send(cmd)
                if rx and len(rx) >= 8:
                    state = "ON" if rx[7] == 1 else "OFF"
                    data[key] = state
                    logger.info(f"   ✓ {label} MOS: {state}")
                else:
                    data[key] = "UNKNOWN"
                time.sleep(0.5)
            
            return data
            
        except Exception as e:
            logger.error(f"BMS read error: {e}", exc_info=True)
            return None
    
    def read_mppt_data(self) -> Optional[Dict]:
        """
        Read MPPT solar charge controller data - Slave 0x01
        """
        slave_id = 0x01
        data = {}
        
        # Read PV Voltage
        pv_voltage_reg = self.read_registers(slave_id, 0x304E, 1, function_code=0x04)
        if pv_voltage_reg:
            data['mppt_pv_voltage'] = round(pv_voltage_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        # Read PV Current
        pv_current_reg = self.read_registers(slave_id, 0x304F, 1, function_code=0x04)
        if pv_current_reg:
            data['mppt_pv_current'] = round(pv_current_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        # Read Battery SOC
        battery_soc_reg = self.read_registers(slave_id, 0x3045, 1, function_code=0x04)
        if battery_soc_reg:
            data['mppt_battery_soc'] = battery_soc_reg[0]
        
        time.sleep(0.05)
        
        # Read Battery Voltage
        battery_voltage_reg = self.read_registers(slave_id, 0x3046, 1, function_code=0x04)
        if battery_voltage_reg:
            data['mppt_battery_voltage'] = round(battery_voltage_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        # Read Battery Current
        battery_current_reg = self.read_registers(slave_id, 0x3047, 1, function_code=0x04)
        if battery_current_reg:
            raw_current = battery_current_reg[0]
            if raw_current > 0x7FFF:
                raw_current = raw_current - 0x10000
            data['mppt_battery_current'] = round(raw_current / 100.0, 2)
        
        # Calculate powers
        if 'mppt_pv_voltage' in data and 'mppt_pv_current' in data:
            data['mppt_pv_power'] = round(data['mppt_pv_voltage'] * data['mppt_pv_current'], 2)
        
        if 'mppt_battery_voltage' in data and 'mppt_battery_current' in data:
            data['mppt_battery_power'] = round(data['mppt_battery_voltage'] * data['mppt_battery_current'], 2)
        
        if data:
            logger.info(f"   ✓ PV: {data.get('mppt_pv_voltage', 0)}V, {data.get('mppt_pv_current', 0)}A, {data.get('mppt_pv_power', 0)}W")
            logger.info(f"   ✓ Battery: {data.get('mppt_battery_voltage', 0)}V, SOC: {data.get('mppt_battery_soc', 0)}%")
        
        return data if data else None
    
    def read_env_data(self) -> Optional[Dict]:
        """Read ENV sensor data - Slave 0x7B"""
        slave_id = 0x7B
        data = {}
        
        # Read CO2 (IEEE754 float, 2 registers)
        co2_reg = self.read_registers(slave_id, 0x0008, 2, function_code=0x03)
        if co2_reg and len(co2_reg) >= 2:
            try:
                co2_bytes = struct.pack('>HH', co2_reg[0], co2_reg[1])
                co2 = struct.unpack('>f', co2_bytes)[0]
                data['env_co2'] = round(co2, 1)
            except:
                pass
        
        time.sleep(0.05)
        
        # Read Temperature
        temp_reg = self.read_registers(slave_id, 0x000E, 2, function_code=0x03)
        if temp_reg and len(temp_reg) >= 2:
            try:
                temp_bytes = struct.pack('>HH', temp_reg[0], temp_reg[1])
                temp = struct.unpack('>f', temp_bytes)[0]
                data['env_temperature'] = round(temp, 1)
            except:
                pass
        
        time.sleep(0.05)
        
        # Read Humidity
        hum_reg = self.read_registers(slave_id, 0x0010, 2, function_code=0x03)
        if hum_reg and len(hum_reg) >= 2:
            try:
                hum_bytes = struct.pack('>HH', hum_reg[0], hum_reg[1])
                hum = struct.unpack('>f', hum_bytes)[0]
                data['env_humidity'] = round(hum, 1)
            except:
                pass
        
        if data:
            logger.info(f"   ✓ Temp: {data.get('env_temperature', 0)}°C, Humidity: {data.get('env_humidity', 0)}%")
            logger.info(f"   ✓ CO2: {data.get('env_co2', 0)} ppm")
        
        return data if data else None
    
    def read_ldr_data(self) -> Optional[Dict]:
        """Read LDR sensor data - Slave 0x04"""
        slave_id = 0x04
        data = {}
        
        # Read LDR value (2 registers = 32-bit)
        ldr_reg = self.read_registers(slave_id, 0x0000, 2, function_code=0x03)
        if ldr_reg and len(ldr_reg) >= 2:
            ldr_value = (ldr_reg[0] << 16) | ldr_reg[1]
            data['ldr_lux'] = ldr_value
            
            if ldr_value > 10000:
                logger.info(f"   ✓ Light: {ldr_value} lux (Bright)")
            elif ldr_value > 1000:
                logger.info(f"   ✓ Light: {ldr_value} lux (Normal)")
            else:
                logger.info(f"   ✓ Light: {ldr_value} lux (Dark)")
        
        return data if data else None
    
    def read_pir_data(self) -> Optional[Dict]:
        """Read PIR sensor data - Slave 0x02"""
        slave_id = 0x02
        data = {}
        
        # Read PIR value
        pir_reg = self.read_registers(slave_id, 0x0000, 1, function_code=0x03)
        if pir_reg:
            motion = bool(pir_reg[0])
            data['pir_motion_detected'] = motion
            logger.info(f"   ✓ {'Motion!' if motion else 'No motion'}")
        
        return data if data else None
    
    def read_all_devices(self) -> Dict:
        """Read all Modbus devices"""
        results = {}
        
        # Read MPPT
        logger.info("📊 Reading MPPT...")
        mppt_data = self.read_mppt_data()
        if mppt_data:
            results.update(mppt_data)
        else:
            logger.warning("   ⚠️  MPPT read failed")
        
        time.sleep(0.3)
        
        # Read ENV sensor
        logger.info("🌡️  Reading ENV sensor...")
        env_data = self.read_env_data()
        if env_data:
            results.update(env_data)
        else:
            logger.warning("   ⚠️  ENV read failed")
        
        time.sleep(0.3)
        
        # Read LDR
        logger.info("💡 Reading LDR...")
        ldr_data = self.read_ldr_data()
        if ldr_data:
            results.update(ldr_data)
        else:
            logger.warning("   ⚠️  LDR read failed")
        
        time.sleep(0.3)
        
        # Read BMS
        logger.info("🔋 Reading BMS...")
        bms_data = self.read_bms_data()
        if bms_data:
            results.update(bms_data)
            logger.info(f"   ✓ Battery: {bms_data.get('bms_battery_voltage', 'N/A')}V, "
                       f"{bms_data.get('bms_battery_current', 'N/A')}A")
            logger.info(f"   ✓ SOC: {bms_data.get('bms_battery_soc', 'N/A')}%, "
                       f"SOH: {bms_data.get('bms_battery_soh', 'N/A')}%")
        else:
            logger.warning("   ⚠️  BMS read failed")
        
        time.sleep(0.3)
        
        # Read PIR
        logger.info("👁️  Reading PIR...")
        pir_data = self.read_pir_data()
        if pir_data:
            results.update(pir_data)
            motion_status = "Motion!" if pir_data['pir_motion_detected'] else "No motion"
            logger.info(f"   ✓ {motion_status}")
        else:
            logger.warning("   ⚠️  PIR read failed")
        
        return results
    
    def save_to_json(self, data: Dict, filename: str = 'sensors.json'):
        """Save sensor data to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Data saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save JSON: {e}")


def main():
    """Main function for testing"""
    reader = ModbusReader(port='/dev/ttyUSB0', baudrate=9600)
    
    if not reader.connect():
        logger.error("Failed to connect to serial port")
        return
    
    try:
        logger.info("🚀 Starting NuGateway Modbus Reader")
        logger.info("📡 Devices: MPPT (0x01), ENV (0x7B), LDR (0x04), BMS (0x3D), PIR (0x02)")
        logger.info("=" * 70)
        
        while True:
            # Read all devices
            data = reader.read_all_devices()
            
            # Save to JSON
            if data:
                reader.save_to_json(data)
                logger.info("=" * 70)
                logger.info(f"✅ Successfully read {len(data)} parameters")
            else:
                logger.warning("⚠️  No data received from any device")
            
            logger.info("=" * 70)
            
            # Wait before next cycle
            time.sleep(10)
            
    except KeyboardInterrupt:
        logger.info("\nℹ️  Stopped by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        reader.disconnect()


if __name__ == '__main__':
    main()
