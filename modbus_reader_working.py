#!/usr/bin/env python3
"""
NuGateway Modbus Reader - Complete Implementation
Reads data from MPPT, ENV sensor, LDR, BMS, and PIR via RS485/Modbus RTU
Based on official register mapping documentation
"""
from config import config_manager
USE_SIM = config_manager.get("use_simulator", False)

# NuGateway patch helpers
def _sim_or_real_reg(sim_reg, real_reg):
    return sim_reg if USE_SIM else real_reg

def _sim_or_real_slave(sim_slave, real_slave):
    return sim_slave if USE_SIM else real_slave


import serial
import time
import logging
import struct
import json
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
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
            logger.info(f"âœ… Connected to {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            logger.error(f"âŒ Failed to open serial port: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("ðŸ”Œ Serial port closed")
    
    @staticmethod
    def calculate_crc(data: List[int]) -> List[int]:
        """
        Calculate Modbus CRC-16 (Little-Endian)
        
        Args:
            data: List of bytes to calculate CRC for
            
        Returns:
            [CRC_LOW, CRC_HIGH]
        """
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
    
    @staticmethod
    def bytes_to_float_ieee754(b1: int, b2: int, b3: int, b4: int) -> float:
        """
        Convert 4 bytes to IEEE 754 float (ABCD format)
        
        Args:
            b1, b2, b3, b4: Four bytes in ABCD order
            
        Returns:
            Float value
        """
        try:
            packed = struct.pack('>BBBB', b1, b2, b3, b4)
            value = struct.unpack('>f', packed)[0]
            return value
        except:
            return 0.0
    
    def read_registers(self, slave_id: int, start_address: int, 
                       count: int, function_code: int = 0x04) -> Optional[List[int]]:
        """
        Read registers from Modbus device
        
        Args:
            slave_id: Device slave ID
            start_address: Starting register address
            count: Number of registers to read
            function_code: Modbus function code (0x03=Holding, 0x04=Input)
            
        Returns:
            List of register values or None on error
        """
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
                    value = (data_bytes[i] << 8) | data_bytes[i + 1]
                    registers.append(value)
            
            return registers
            
        except Exception as e:
            logger.error(f"Error reading from slave {slave_id:02X}: {e}")
            return None
    
    def read_mppt_data(self) -> Optional[Dict]:
        """
        Read MPPT solar charge controller data - Slave 0x0A
        Using CORRECT register addresses from telemetry
        """
        slave_id = _sim_or_real_slave(0x03, 0x01)
        data = {}
        
        # Read PV (Solar Panel) Data
        pv_voltage_reg = self.read_registers(slave_id, _sim_or_real_reg(0x3000, 0x304E), 1, function_code=0x04)
        if pv_voltage_reg:
            data['mppt_pv_voltage'] = round(pv_voltage_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        pv_current_reg = self.read_registers(slave_id, _sim_or_real_reg(0x3001, 0x304F), 1, function_code=0x04)
        if pv_current_reg:
            data['mppt_pv_current'] = round(pv_current_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        # PV Power (32-bit)
        pv_power_reg = self.read_registers(slave_id, 0x3050, 2, function_code=0x04)
        if pv_power_reg and len(pv_power_reg) >= 2:
            pv_power = (pv_power_reg[0] << 16) | pv_power_reg[1]
            data['mppt_pv_power'] = round(pv_power / 100.0, 2)
        
        time.sleep(0.05)
        
        # Read Battery Data
        battery_soc_reg = self.read_registers(slave_id, 0x3045, 1, function_code=0x04)
        if battery_soc_reg:
            data['mppt_battery_soc'] = battery_soc_reg[0]
        
        time.sleep(0.05)
        
        battery_voltage_reg = self.read_registers(slave_id, 0x3046, 1, function_code=0x04)
        if battery_voltage_reg:
            data['mppt_battery_voltage'] = round(battery_voltage_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        battery_current_reg = self.read_registers(slave_id, 0x3047, 1, function_code=0x04)
        if battery_current_reg:
            # Handle signed value
            raw_current = battery_current_reg[0]
            if raw_current > 0x7FFF:
                raw_current = raw_current - 0x10000
            data['mppt_battery_current'] = round(raw_current / 100.0, 2)
        
        time.sleep(0.05)
        
        # Battery Power (32-bit)
        battery_power_reg = self.read_registers(slave_id, 0x3048, 2, function_code=0x04)
        if battery_power_reg and len(battery_power_reg) >= 2:
            battery_power = (battery_power_reg[0] << 16) | battery_power_reg[1]
            # Handle signed 32-bit
            if battery_power > 0x7FFFFFFF:
                battery_power = battery_power - 0x100000000
            data['mppt_battery_power'] = round(battery_power / 100.0, 2)
        
        time.sleep(0.05)
        
        # Read Load Data
        load_voltage_reg = self.read_registers(slave_id, 0x304A, 1, function_code=0x04)
        if load_voltage_reg:
            data['mppt_load_voltage'] = round(load_voltage_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        load_current_reg = self.read_registers(slave_id, 0x304B, 1, function_code=0x04)
        if load_current_reg:
            data['mppt_load_current'] = round(load_current_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        # Load Power (32-bit)
        load_power_reg = self.read_registers(slave_id, 0x304C, 2, function_code=0x04)
        if load_power_reg and len(load_power_reg) >= 2:
            load_power = (load_power_reg[0] << 16) | load_power_reg[1]
            data['mppt_load_power'] = round(load_power / 100.0, 2)
        
        time.sleep(0.05)
        
        # Read Temperatures
        internal_temp_reg = self.read_registers(slave_id, 0x3036, 1, function_code=0x04)
        if internal_temp_reg:
            data['mppt_internal_temp'] = round(internal_temp_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        env_temp_reg = self.read_registers(slave_id, 0x3037, 1, function_code=0x04)
        if env_temp_reg:
            data['mppt_env_temp'] = round(env_temp_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        # Read Status
        charge_status_reg = self.read_registers(slave_id, 0x3034, 1, function_code=0x04)
        if charge_status_reg:
            status_code = charge_status_reg[0]
            status_map = {
                0: "Not charging",
                1: "Float",
                2: "Boost",
                3: "Equalization"
            }
            data['mppt_charge_status'] = status_map.get(status_code, f"Unknown ({status_code})")
        
        time.sleep(0.05)
        
        # Read Energy Data
        daily_pv_energy_reg = self.read_registers(slave_id, 0x3052, 1, function_code=0x04)
        if daily_pv_energy_reg:
            data['mppt_daily_pv_energy'] = round(daily_pv_energy_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        total_pv_energy_reg = self.read_registers(slave_id, 0x3053, 1, function_code=0x04)
        if total_pv_energy_reg:
            data['mppt_total_pv_energy'] = round(total_pv_energy_reg[0] / 100.0, 2)
        
        time.sleep(0.05)
        
        # Read Running Days
        running_days_reg = self.read_registers(slave_id, 0x3031, 1, function_code=0x04)
        if running_days_reg:
            data['mppt_running_days'] = running_days_reg[0]
        
        if not data:
            return None
        
        # Determine overall status
        if 'mppt_pv_current' in data and data['mppt_pv_current'] > 0.1:
            if 'mppt_battery_voltage' in data and data['mppt_battery_voltage'] > 0:
                data['mppt_status'] = "Charging"
            else:
                data['mppt_status'] = "Active"
        elif 'mppt_pv_voltage' in data and data['mppt_pv_voltage'] > 5.0:
            data['mppt_status'] = "Standby"
        else:
            data['mppt_status'] = "Night"
        
        return data
    
    def read_env_data(self) -> Optional[Dict]:
        """Read environmental sensor data - Slave 0x7B (123)"""
        slave_id = 0x7B
        data = {}
        
        # Read CO2 (0x0020 based on corrected mapping)
        co2_raw = self.read_registers(slave_id, _sim_or_real_reg(0x0008, 0x0020), 2, function_code=0x03)
        if co2_raw and len(co2_raw) >= 2:
            b1 = (co2_raw[0] >> 8) & 0xFF
            b2 = co2_raw[0] & 0xFF
            b3 = (co2_raw[1] >> 8) & 0xFF
            b4 = co2_raw[1] & 0xFF
            data['env_co2'] = round(self.bytes_to_float_ieee754(b1, b2, b3, b4), 2)
        
        time.sleep(0.1)
        
        # Read Temperature (0x0024)
        temp_raw = self.read_registers(slave_id, _sim_or_real_reg(0x000E, 0x0024), 2, function_code=0x03)
        if temp_raw and len(temp_raw) >= 2:
            b1 = (temp_raw[0] >> 8) & 0xFF
            b2 = temp_raw[0] & 0xFF
            b3 = (temp_raw[1] >> 8) & 0xFF
            b4 = temp_raw[1] & 0xFF
            data['env_temperature'] = round(self.bytes_to_float_ieee754(b1, b2, b3, b4), 2)
        
        time.sleep(0.1)
        
        # Read Humidity (0x0024 + 2 = would be in same read, but let's read separately)
        # Actually temperature and humidity might be consecutive, adjust if needed
        hum_raw = self.read_registers(slave_id, _sim_or_real_reg(0x0010, 0x0026), 2, function_code=0x03)
        if hum_raw and len(hum_raw) >= 2:
            b1 = (hum_raw[0] >> 8) & 0xFF
            b2 = hum_raw[0] & 0xFF
            b3 = (hum_raw[1] >> 8) & 0xFF
            b4 = hum_raw[1] & 0xFF
            data['env_humidity'] = round(self.bytes_to_float_ieee754(b1, b2, b3, b4), 2)
        
        time.sleep(0.1)
        
        # Read PM2.5 (0x0022)
        pm25_raw = self.read_registers(slave_id, _sim_or_real_reg(0x000A, 0x0022), 2, function_code=0x03)
        if pm25_raw and len(pm25_raw) >= 2:
            b1 = (pm25_raw[0] >> 8) & 0xFF
            b2 = pm25_raw[0] & 0xFF
            b3 = (pm25_raw[1] >> 8) & 0xFF
            b4 = pm25_raw[1] & 0xFF
            data['env_pm2_5'] = round(self.bytes_to_float_ieee754(b1, b2, b3, b4), 2)
        
        time.sleep(0.1)
        
        # Read PM10 (would be next register, but documentation says 0x000C for PM10)
        # Let's try original 0x000C
        pm10_raw = self.read_registers(slave_id, 0x000C, 2, function_code=0x03)
        if pm10_raw and len(pm10_raw) >= 2:
            b1 = (pm10_raw[0] >> 8) & 0xFF
            b2 = pm10_raw[0] & 0xFF
            b3 = (pm10_raw[1] >> 8) & 0xFF
            b4 = pm10_raw[1] & 0xFF
            data['env_pm10'] = round(self.bytes_to_float_ieee754(b1, b2, b3, b4), 2)
        
        time.sleep(0.1)
        
        # Read Illumination (0x0012)
        lux_raw = self.read_registers(slave_id, 0x0012, 2, function_code=0x03)
        if lux_raw and len(lux_raw) >= 2:
            b1 = (lux_raw[0] >> 8) & 0xFF
            b2 = lux_raw[0] & 0xFF
            b3 = (lux_raw[1] >> 8) & 0xFF
            b4 = lux_raw[1] & 0xFF
            data['env_illumination'] = round(self.bytes_to_float_ieee754(b1, b2, b3, b4), 2)
        
        if not data:
            return None
        
        # Calculate air quality score
        air_quality_score = 0
        if 'env_pm2_5' in data:
            if data['env_pm2_5'] < 12:
                air_quality_score = 0  # MÃ¼kemmel
            elif data['env_pm2_5'] < 35:
                air_quality_score = 1  # Ä°yi
            else:
                air_quality_score = 2  # Orta
        
        data['env_air_quality_score'] = air_quality_score
        
        return data
    
    def read_ldr_data(self) -> Optional[Dict]:
        """Read LDR light sensor data - Slave 0x04"""
        slave_id = _sim_or_real_slave(0x01, 0x04)
        
        # Read light level (0x0000, 2 registers = 4 bytes)
        light_raw = self.read_registers(slave_id, 0x0000, 2, function_code=0x03)
        
        if not light_raw or len(light_raw) < 2:
            return None
        
        # Combine 4 bytes to get lux value
        lux_value = (light_raw[0] << 16) | light_raw[1]
        
        # Determine if dark
        is_dark = lux_value < 50
        
        return {
            'ldr_lux': lux_value,
            'ldr_is_dark': is_dark
        }
    
    def read_bms_data(self) -> Optional[Dict]:
        """
        Read BMS (Battery Management System) data - Custom Protocol
        Frame Format: [0x3D][SRC][DST][CMD][R/W][LEN_H][LEN_L][CHECKSUM]
        BMS Destination Address: 0x02
        Baudrate: 9600 bps
        """
        if not self.serial or not self.serial.is_open:
            logger.error("Serial port not open")
            return None
        
        try:
            # Build BMS request frame for real-time data (0x00)
            frame = [
                0x3D,  # Frame header
                0x01,  # Source address (Host)
                0x02,  # Destination address (BMS)
                0x00,  # Command address (0x00 = Real-time info)
                0x01,  # R/W: 1 = Read
                0x00,  # Data length high byte
                0x00   # Data length low byte
            ]
            
            # Calculate checksum (simple sum of all bytes)
            checksum = sum(frame) & 0xFF
            frame.append(checksum)
            
            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Send request
            self.serial.write(bytes(frame))
            logger.debug(f"BMS TX: {' '.join([f'{b:02X}' for b in frame])}")
            
            # Wait for response
            time.sleep(0.2)
            
            # Read response (header + data)
            response = list(self.serial.read(200))
            
            if not response or len(response) < 10:
                logger.warning("BMS: No response or too short")
                return None
            
            logger.debug(f"BMS RX: {' '.join([f'{b:02X}' for b in response[:20]])}...")
            
            # Parse response header
            if response[0] != 0x3D:
                logger.error("BMS: Invalid frame header")
                return None
            
            # Extract data length
            data_len = (response[5] << 8) | response[6]
            
            # Verify we have enough data
            if len(response) < 7 + data_len + 1:
                logger.error("BMS: Incomplete response")
                return None
            
            # Extract payload
            payload = response[7:7+data_len]
            
            # Parse real-time data (0x00 command response)
            data = {}
            idx = 0
            
            # Skip cell voltages (24 cells x 2 bytes = 48 bytes)
            idx += 48
            
            # Total voltage (2 bytes, unit: 10mV)
            if idx + 2 <= len(payload):
                total_voltage = ((payload[idx] << 8) | payload[idx+1]) * 0.01
                data['bms_battery_voltage'] = round(total_voltage, 2)
                idx += 2
            
            # Total current (2 bytes, unit: 10mA, signed)
            if idx + 2 <= len(payload):
                raw_current = (payload[idx] << 8) | payload[idx+1]
                # Handle signed value
                if raw_current > 0x7FFF:
                    raw_current = raw_current - 0x10000
                total_current = raw_current * 0.01
                data['bms_battery_current'] = round(total_current, 2)
                idx += 2
            
            # Calculate battery power
            if 'bms_battery_voltage' in data and 'bms_battery_current' in data:
                data['bms_battery_power'] = round(data['bms_battery_voltage'] * data['bms_battery_current'], 2)
            
            # Temperatures (3 sensors x 2 bytes, unit: 0.1Â°C)
            if idx + 6 <= len(payload):
                temp1 = ((payload[idx] << 8) | payload[idx+1]) * 0.1
                data['bms_battery_temp'] = round(temp1, 2)
                idx += 6
            
            # SOC (State of Charge, 1 byte, %)
            if idx + 1 <= len(payload):
                data['bms_battery_soc'] = payload[idx]
                idx += 1
            
            # SOH (State of Health, 1 byte, %)
            if idx + 1 <= len(payload):
                data['bms_battery_soh'] = payload[idx]
                idx += 1
            
            # Remaining capacity (4 bytes, unit: mAH)
            if idx + 4 <= len(payload):
                remaining_cap = ((payload[idx] << 24) | (payload[idx+1] << 16) | 
                               (payload[idx+2] << 8) | payload[idx+3])
                idx += 4
            
            # Maximum capacity (4 bytes, unit: mAH)
            if idx + 4 <= len(payload):
                max_cap = ((payload[idx] << 24) | (payload[idx+1] << 16) | 
                          (payload[idx+2] << 8) | payload[idx+3])
                idx += 4
                
                # Calculate discharge/charge time (rough estimate)
                if 'bms_battery_current' in data and data['bms_battery_current'] != 0:
                    if data['bms_battery_current'] < 0:  # Discharging
                        data['bms_discharge_time'] = int(abs(remaining_cap / (data['bms_battery_current'] * 1000)))
                        data['bms_charge_time'] = 0
                    else:  # Charging
                        data['bms_charge_time'] = int((max_cap - remaining_cap) / (data['bms_battery_current'] * 1000))
                        data['bms_discharge_time'] = 0
                else:
                    data['bms_discharge_time'] = 0
                    data['bms_charge_time'] = 0
            
            # BMS low power mode
            data['bms_low_power_mode'] = data.get('bms_battery_soc', 100) < 20
            
            return data
            
        except Exception as e:
            logger.error(f"Error reading BMS data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def write_register(self, slave_id: int, address: int, value: int, 
                      function_code: int = 0x06) -> bool:
        """
        Write single register to Modbus device
        
        Args:
            slave_id: Device slave ID
            address: Register address
            value: Value to write (16-bit)
            function_code: 0x06 for single register
            
        Returns:
            True if successful, False otherwise
        """
        if not self.serial or not self.serial.is_open:
            logger.error("Serial port not open")
            return False
        
        # Build request
        request = [
            slave_id,
            function_code,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF
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
            logger.debug(f"WRITE TX: {' '.join([f'{b:02X}' for b in request])}")
            
            # Wait for response
            time.sleep(0.1)
            
            # Read response (should echo back the request)
            response = list(self.serial.read(8))
            
            if not response:
                logger.error(f"No write response from slave {slave_id:02X}")
                return False
            
            logger.debug(f"WRITE RX: {' '.join([f'{b:02X}' for b in response])}")
            
            # Verify CRC
            if not self.verify_crc(response):
                logger.error(f"CRC error in write response from slave {slave_id:02X}")
                return False
            
            # Check if response matches request (successful write)
            if response[:6] == request[:6]:
                logger.info(f"âœ… Successfully wrote {value} to register 0x{address:04X}")
                return True
            else:
                logger.error(f"Write verification failed")
                return False
                
        except Exception as e:
            logger.error(f"Error writing to slave {slave_id:02X}: {e}")
            return False
    
    def set_mppt_dimming(self, percentage: int) -> bool:
        """
        Set MPPT dimming level
        
        Args:
            percentage: 0-100 (will be mapped to 0-10)
            
        Returns:
            True if successful
        """
        if not 0 <= percentage <= 100:
            logger.error(f"Invalid dimming percentage: {percentage}")
            return False
        
        # Map 0-100% to 0-10 value
        value = int(percentage / 10)
        
        return self.write_register(0x0A, 0x9041, value, function_code=0x06)
    
    def set_mppt_rtc(self, year: int, month: int, day: int, 
                     hour: int, minute: int, second: int) -> bool:
        """
        Set MPPT RTC (Real-Time Clock)
        
        Args:
            year: 0-99 (last 2 digits)
            month: 1-12
            day: 1-31
            hour: 0-23
            minute: 0-59
            second: 0-59
            
        Returns:
            True if all writes successful
        """
        rtc_registers = [
            (0x9017, second),
            (0x9018, minute),
            (0x9019, hour),
            (0x901A, day),
            (0x901B, month),
            (0x901C, year % 100)
        ]
        
        for address, value in rtc_registers:
            if not self.write_register(0x0A, address, value, function_code=0x06):
                logger.error(f"Failed to write RTC register 0x{address:04X}")
                return False
            time.sleep(0.05)
        
        logger.info(f"âœ… RTC set to: 20{year:02d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")
        return True
    
    def set_mppt_timer(self, timer_num: int, duration_index: int, dimming_index: int) -> bool:
        """
        Set MPPT Timer (1-5)
        
        Args:
            timer_num: 1-5
            duration_index: 0-15 (maps to minutes: 0,30,60,90...450)
            dimming_index: 0-10 (maps to 0%,10%,20%...100%)
            
        Returns:
            True if successful
        """
        if not 1 <= timer_num <= 5:
            logger.error(f"Invalid timer number: {timer_num}")
            return False
        
        if not 0 <= duration_index <= 15:
            logger.error(f"Invalid duration index: {duration_index}")
            return False
        
        if not 0 <= dimming_index <= 10:
            logger.error(f"Invalid dimming index: {dimming_index}")
            return False
        
        # Calculate register addresses
        # Timer 1: 0x9040 (duration), 0x9041 (dimming)
        # Timer 2: 0x9042, 0x9043
        # etc.
        base_addr = 0x9040 + ((timer_num - 1) * 2)
        
        # Write duration
        if not self.write_register(0x0A, base_addr, duration_index, function_code=0x06):
            return False
        
        time.sleep(0.05)
        
        # Write dimming
        if not self.write_register(0x0A, base_addr + 1, dimming_index, function_code=0x06):
            return False
        
        duration_map = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360, 390, 420, 450]
        duration_min = duration_map[duration_index] if duration_index < len(duration_map) else 0
        
        logger.info(f"âœ… Timer {timer_num} set: {duration_min}min @ {dimming_index*10}%")
        return True
    
    def set_mppt_timed_schedule(self, period_num: int, 
                                start_h: int, start_m: int, start_s: int,
                                off_h: int, off_m: int, off_s: int) -> bool:
        """
        Set MPPT Timed Start/Stop Schedule (Period 1 or 2)
        
        Args:
            period_num: 1 or 2
            start_h, start_m, start_s: Start time
            off_h, off_m, off_s: Off time
            
        Returns:
            True if successful
        """
        if period_num not in [1, 2]:
            logger.error(f"Invalid period: {period_num}")
            return False
        
        # Period 1: 0x902F-0x9034, Period 2: 0x9035-0x903A
        base_start = 0x902F if period_num == 1 else 0x9035
        base_off = 0x9032 if period_num == 1 else 0x9038
        
        registers = [
            (base_start, start_s),
            (base_start + 1, start_m),
            (base_start + 2, start_h),
            (base_off, off_s),
            (base_off + 1, off_m),
            (base_off + 2, off_h)
        ]
        
        for addr, value in registers:
            if not self.write_register(0x0A, addr, value, function_code=0x06):
                logger.error(f"Failed to write schedule register 0x{addr:04X}")
                return False
            time.sleep(0.05)
        
        logger.info(f"âœ… Schedule {period_num} set: ON {start_h:02d}:{start_m:02d} â†’ OFF {off_h:02d}:{off_m:02d}")
        return True
    
    def set_battery_settings(self, lvd_voltage: float, lvr_voltage: float,
                            boost_voltage: float, float_voltage: float) -> bool:
        """
        Set battery voltage settings
        
        Args:
            lvd_voltage: Low Voltage Disconnect (V)
            lvr_voltage: Low Voltage Recovery (V)
            boost_voltage: Boost charge voltage (V)
            float_voltage: Float charge voltage (V)
            
        Returns:
            True if successful
        """
        settings = [
            (0x9022, int(lvd_voltage * 100)),
            (0x9023, int(lvr_voltage * 100)),
            (0x9024, int(boost_voltage * 100)),
            (0x9026, int(float_voltage * 100))
        ]
        
        for addr, value in settings:
            if not self.write_register(0x0A, addr, value, function_code=0x06):
                logger.error(f"Failed to write battery setting 0x{addr:04X}")
                return False
            time.sleep(0.05)
        
        logger.info(f"âœ… Battery settings: LVD={lvd_voltage}V, LVR={lvr_voltage}V, Boost={boost_voltage}V, Float={float_voltage}V")
        return True
    
    def write_coil(self, slave_id: int, coil_address: int, value: bool) -> bool:
        """
        Write single coil (Function Code 0x05)
        
        Args:
            slave_id: Device slave ID
            coil_address: Coil address
            value: True=ON (0xFF00), False=OFF (0x0000)
            
        Returns:
            True if successful
        """
        if not self.serial or not self.serial.is_open:
            logger.error("Serial port not open")
            return False
        
        # Build request
        coil_value = 0xFF00 if value else 0x0000
        request = [
            slave_id,
            0x05,  # Function code: Write Single Coil
            (coil_address >> 8) & 0xFF,
            coil_address & 0xFF,
            (coil_value >> 8) & 0xFF,
            coil_value & 0xFF
        ]
        
        # Add CRC
        crc = self.calculate_crc(request)
        request.extend(crc)
        
        try:
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.serial.write(bytes(request))
            logger.debug(f"COIL TX: {' '.join([f'{b:02X}' for b in request])}")
            
            time.sleep(0.1)
            response = list(self.serial.read(8))
            
            if not response:
                logger.error(f"No coil response from slave {slave_id:02X}")
                return False
            
            if not self.verify_crc(response):
                logger.error(f"CRC error in coil response")
                return False
            
            logger.info(f"âœ… Coil 0x{coil_address:04X} set to {'ON' if value else 'OFF'}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing coil: {e}")
            return False
    
    def factory_reset_mppt(self) -> bool:
        """Factory reset MPPT (Coil 0x0008)"""
        return self.write_coil(0x0A, 0x0008, True)
    
    def clear_statistics_mppt(self) -> bool:
        """Clear statistics counters (Coil 0x0009)"""
        return self.write_coil(0x0A, 0x0009, True)
    
    def enable_timing_control(self, enable: bool) -> bool:
        """Enable/disable timing control mode (Coil 0x0002)"""
        return self.write_coil(0x0A, 0x0002, enable)
    
    def get_mppt_rtc(self) -> Optional[Dict]:
        """
        Read MPPT RTC (Real-Time Clock)
        
        Returns:
            Dict with datetime components or None
        """
        # Read RTC registers (0x9017-0x901C, 6 registers)
        rtc_data = self.read_registers(0x0A, 0x9017, 6, function_code=0x03)
        
        if not rtc_data or len(rtc_data) < 6:
            return None
        
        return {
            'second': rtc_data[0],
            'minute': rtc_data[1],
            'hour': rtc_data[2],
            'day': rtc_data[3],
            'month': rtc_data[4],
            'year': 2000 + rtc_data[5]
        }
    
    def read_pir_data(self) -> Optional[Dict]:
        """
        Read PIR motion sensor data - Slave 0x02
        """
        slave_id = 0x02
        
        # Read infrared sensor status (0x0006)
        ir_status = self.read_registers(slave_id, 0x0006, 1, function_code=0x03)
        
        if not ir_status:
            return None
        
        # Read radar detection status (0x0007)
        radar_status = self.read_registers(slave_id, 0x0007, 1, function_code=0x03)
        
        return {
            'pir_motion_detected': ir_status[0] == 1 if ir_status else False,
            'pir_radar_detected': radar_status[0] == 1 if radar_status else False
        }
    
    def read_all_devices(self) -> Dict:
        """Read data from all configured devices"""
        results = {}
        
        # Read MPPT
        logger.info("ðŸ“Š Reading MPPT...")
        mppt_data = self.read_mppt_data()
        if mppt_data:
            results.update(mppt_data)
            logger.info(f"   âœ“ PV: {mppt_data.get('mppt_pv_voltage', 'N/A')}V, "
                       f"{mppt_data.get('mppt_pv_current', 'N/A')}A, "
                       f"{mppt_data.get('mppt_pv_power', 'N/A')}W")
            logger.info(f"   âœ“ Battery: {mppt_data.get('mppt_battery_voltage', 'N/A')}V, "
                       f"SOC: {mppt_data.get('mppt_battery_soc', 'N/A')}%")
        else:
            logger.warning("   âš ï¸  MPPT read failed")
        
        time.sleep(0.3)
        
        # Read ENV sensor
        logger.info("ðŸŒ¡ï¸  Reading ENV sensor...")
        env_data = self.read_env_data()
        if env_data:
            results.update(env_data)
            logger.info(f"   âœ“ Temp: {env_data.get('env_temperature', 'N/A')}Â°C, "
                       f"Humidity: {env_data.get('env_humidity', 'N/A')}%")
            logger.info(f"   âœ“ CO2: {env_data.get('env_co2', 'N/A')} ppm")
        else:
            logger.warning("   âš ï¸  ENV read failed")
        
        time.sleep(0.3)
        
        # Read LDR
        logger.info("ðŸ’¡ Reading LDR...")
        ldr_data = self.read_ldr_data()
        if ldr_data:
            results.update(ldr_data)
            logger.info(f"   âœ“ Light: {ldr_data['ldr_lux']} lux "
                       f"({'Dark' if ldr_data['ldr_is_dark'] else 'Bright'})")
        else:
            logger.warning("   âš ï¸  LDR read failed")
        
        time.sleep(0.3)
        
        # Read BMS
        logger.info("ðŸ”‹ Reading BMS...")
        bms_data = self.read_bms_data()
        if bms_data:
            results.update(bms_data)
            logger.info(f"   âœ“ Battery: {bms_data.get('bms_battery_voltage', 'N/A')}V, "
                       f"{bms_data.get('bms_battery_current', 'N/A')}A")
            logger.info(f"   âœ“ SOC: {bms_data.get('bms_battery_soc', 'N/A')}%, "
                       f"SOH: {bms_data.get('bms_battery_soh', 'N/A')}%")
        else:
            logger.warning("   âš ï¸  BMS read failed")
        
        time.sleep(0.3)
        
        # Read PIR
        logger.info("ðŸ‘ï¸  Reading PIR...")
        pir_data = self.read_pir_data()
        if pir_data:
            results.update(pir_data)
            motion_status = "Motion!" if pir_data['pir_motion_detected'] else "No motion"
            logger.info(f"   âœ“ {motion_status}")
        else:
            logger.warning("   âš ï¸  PIR read failed")
        
        return results
    
    def save_to_json(self, data: Dict, filename: str = 'sensors.json'):
        """Save sensor data to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"ðŸ’¾ Data saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save JSON: {e}")


def main():
    """Main function for testing"""
    reader = ModbusReader(port='/dev/ttyAMA0', baudrate=9600)
    
    if not reader.connect():
        logger.error("Failed to connect to serial port")
        return
    
    try:
        logger.info("ðŸš€ Starting NuGateway Modbus Reader")
        logger.info("ðŸ“¡ Devices: MPPT (0x01), ENV (0x7B), LDR (0x04), BMS (0x02), PIR (0x02)")
        logger.info("=" * 70)
        
        while True:
            # Read all devices
            data = reader.read_all_devices()
            
            # Save to JSON
            if data:
                reader.save_to_json(data)
                logger.info("=" * 70)
                logger.info(f"âœ… Successfully read {len(data)} parameters")
            else:
                logger.warning("âš ï¸  No data received from any device")
            
            logger.info("=" * 70)
            
            # Wait before next cycle
            time.sleep(10)
            
    except KeyboardInterrupt:
        logger.info("\nâ¹ï¸  Stopped by user")
    except Exception as e:
        logger.error(f"âŒ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        reader.disconnect()


if __name__ == '__main__':
    main()
