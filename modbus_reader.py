from pymodbus.client import ModbusSerialClient
import struct
import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from relay_control import apply_logic
from config import config_manager
from logger import sensor_logger, setup_logging
from alarm_system import AlarmSystem
from mqtt_client import MQTTClient

# Setup logging
setup_logging(
    log_level=config_manager.get('log_level', 'INFO'),
    log_file=config_manager.get('log_file', 'nugateway.log')
)
logger = logging.getLogger(__name__)

SENSOR_FILE = "sensors.json"

class SensorCache:
    """Simple cache for sensor data with TTL"""
    
    def __init__(self, ttl_seconds: int = 5):
        self.cache: Dict[str, Any] = {}
        self.timestamps: Dict[str, datetime] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        if key in self.cache:
            if datetime.now() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None
    
    def set(self, key: str, value: Any):
        """Set cache value with current timestamp"""
        self.cache[key] = value
        self.timestamps[key] = datetime.now()

# Global cache instance
sensor_cache = SensorCache()

def read_float32_ieee754(registers) -> float:
    """Convert two 16-bit registers to IEEE 754 float"""
    try:
        combined = (registers[0] << 16) | registers[1]
        return struct.unpack('>f', combined.to_bytes(4, byteorder='big'))[0]
    except Exception as e:
        logger.error(f"Float conversion error: {e}")
        return 0.0

def classify_air_quality(pm2_5: float, co2: float) -> tuple:
    """Classify air quality based on PM2.5 and CO2 levels"""
    score = 0
    
    if pm2_5 > 55:
        score += 2
    elif pm2_5 > 35:
        score += 1
    
    if co2 > 2000:
        score += 2
    elif co2 > 1200:
        score += 1
    
    levels = {
        0: ("Mükemmel", 0),
        1: ("Orta", 25),
        2: ("Düşük kalite", 50),
        3: ("Kötü", 75),
        4: ("Sağlıksız", 100)
    }
    
    return levels.get(score, ("Bilinmiyor", 0))

def estimate_weather(temp: float, humidity: float, lux: int) -> str:
    """Estimate weather condition based on sensor data"""
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

def read_sensor_safe(client, address: int, count: int, slave: int, 
                     register_type: str = 'holding') -> Optional[Any]:
    """Safe sensor reading with error handling and caching"""
    cache_key = f"{slave}_{address}_{count}_{register_type}"
    
    # Check cache first
    cached = sensor_cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        if register_type == 'holding':
            result = client.read_holding_registers(address, count, slave=slave)
        else:  # input registers
            result = client.read_input_registers(address, count, slave=slave)
        
        if not result.isError():
            sensor_cache.set(cache_key, result)
            return result
        else:
            logger.warning(f"Modbus error at slave={slave}, addr={address}: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Exception reading slave={slave}, addr={address}: {e}")
        return None

def read_sensors(alarm_system: Optional[AlarmSystem] = None,
                mqtt_client: Optional[MQTTClient] = None) -> Dict[str, Any]:
    """Read all sensors and return data dictionary"""
    
    # Load configuration
    config = config_manager.config
    port = config.serial_port
    baudrate = config.baudrate
    
    logger.info(f"Connecting to Modbus on {port} @ {baudrate} baud")
    
    # Create Modbus client
    client = ModbusSerialClient(
        method="rtu",
        port=port,
        baudrate=baudrate,
        timeout=2,
        stopbits=config.stop_bits,
        bytesize=config.data_bits,
        parity=config.parity
    )
    
    if not client.connect():
        logger.error("❌ Modbus connection failed!")
        return {}
    
    result = {}
    
    # === LDR Sensor (Slave 1) ===
    try:
        r = read_sensor_safe(client, 0x0000, 2, 1, 'holding')
        if r:
            lux = (r.registers[0] << 16) | r.registers[1]
            result["ldr_lux"] = lux
            result["is_dark"] = lux < 20000
            logger.debug(f"LDR: {lux} lux")
    except Exception as e:
        logger.error(f"LDR Exception: {e}")
    
    # === Environmental Sensor (Slave 123) ===
    try:
        co2 = read_sensor_safe(client, 0x0008, 2, 123, 'holding')
        temp = read_sensor_safe(client, 0x000E, 2, 123, 'holding')
        hum = read_sensor_safe(client, 0x0010, 2, 123, 'holding')
        pm25 = read_sensor_safe(client, 0x000A, 2, 123, 'holding')
        pm10 = read_sensor_safe(client, 0x000C, 2, 123, 'holding')
        illumination = read_sensor_safe(client, 0x0012, 2, 123, 'holding')
        
        if all([co2, temp, hum, pm25, pm10, illumination]):
            co2_val = read_float32_ieee754(co2.registers)
            temp_val = read_float32_ieee754(temp.registers)
            hum_val = read_float32_ieee754(hum.registers)
            pm25_val = read_float32_ieee754(pm25.registers)
            pm10_val = read_float32_ieee754(pm10.registers)
            illum_val = read_float32_ieee754(illumination.registers)
            
            result["co2"] = round(co2_val, 2)
            result["temperature"] = round(temp_val, 2)
            result["humidity"] = round(hum_val, 2)
            result["pm2_5"] = round(pm25_val, 2)
            result["pm10"] = round(pm10_val, 2)
            result["illumination"] = round(illum_val, 2)
            
            air_text, air_score = classify_air_quality(pm25_val, co2_val)
            result["air_quality"] = air_text
            result["air_quality_score"] = air_score
            
            lux = result.get("ldr_lux", 0)
            result["weather_status"] = estimate_weather(temp_val, hum_val, lux)
            
            logger.debug(f"EnvSensor: T={temp_val}°C, H={hum_val}%, CO2={co2_val}ppm")
        else:
            logger.warning("EnvSensor: incomplete data")
    except Exception as e:
        logger.error(f"EnvSensor Exception: {e}")
    
    # === MPPT Charge Controller (Slave 3) ===
    try:
        pv_v = read_sensor_safe(client, 0x3000, 1, 3, 'input')
        pv_c = read_sensor_safe(client, 0x3001, 1, 3, 'input')
        
        if pv_v and pv_c:
            volt = pv_v.registers[0] / 100.0
            curr = pv_c.registers[0] / 100.0
            result["pv_voltage"] = round(volt, 2)
            result["pv_current"] = round(curr, 2)
            result["pv_power"] = round(volt * curr, 2)
            result["mppt_status"] = "Charging" if curr > 0.1 else "Idle"
            logger.debug(f"MPPT: {volt}V, {curr}A, {volt*curr}W")
    except Exception as e:
        logger.error(f"MPPT Exception: {e}")
    
    # === PIR Motion Sensor (Slave 2) ===
    try:
        pir = read_sensor_safe(client, 0x0006, 1, 2, 'holding')
        if pir:
            pir_value = pir.registers[0]
            result["motion_detected"] = pir_value == 1
            result["display_should_be_on"] = pir_value == 1
            logger.debug(f"PIR: {'Motion' if pir_value == 1 else 'No motion'}")
    except Exception as e:
        logger.error(f"PIR Exception: {e}")
    
    # === BMS Battery Management (Slave 4) ===
    try:
        bv = read_sensor_safe(client, 0x3004, 1, 4, 'input')
        bc = read_sensor_safe(client, 0x3005, 1, 4, 'input')
        soc = read_sensor_safe(client, 0x3020, 1, 4, 'input')
        soh = read_sensor_safe(client, 0x3021, 1, 4, 'input')
        bt = read_sensor_safe(client, 0x3022, 1, 4, 'input')
        dt = read_sensor_safe(client, 0x3023, 1, 4, 'input')
        ct = read_sensor_safe(client, 0x3024, 1, 4, 'input')
        
        if bv and bc:
            voltage = bv.registers[0] / 100.0
            current = bc.registers[0] / 100.0
            result["battery_voltage"] = round(voltage, 2)
            result["battery_current"] = round(current, 2)
            result["battery_power"] = round(voltage * current, 2)
        
        if soc:
            result["battery_soc"] = soc.registers[0]
        if soh:
            result["battery_soh"] = soh.registers[0]
        if bt:
            result["battery_temp"] = bt.registers[0] / 10.0
        if dt:
            result["discharge_time"] = dt.registers[0]
        if ct:
            result["charge_time"] = ct.registers[0]
        
        result["bms_low_power_mode"] = result.get("battery_soc", 100) < 30
        
        logger.debug(f"BMS: {result.get('battery_voltage')}V, SOC={result.get('battery_soc')}%")
        
    except Exception as e:
        logger.error(f"BMS Exception: {e}")
    
    client.close()
    
    # Save to JSON file
    try:
        with open(SENSOR_FILE, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"✅ Data saved to {SENSOR_FILE}")
    except Exception as e:
        logger.error(f"Failed to save sensor data: {e}")
    
    # Log sensor data
    if config_manager.get('enable_data_logging', True):
        sensor_logger.log(result)
    
    # Check alarms
    if alarm_system:
        alarms = alarm_system.check_alarms(result)
        if alarms and mqtt_client and mqtt_client.is_connected():
            for alarm in alarms:
                mqtt_client.publish_alarm(alarm.__dict__)
    
    # Publish to MQTT
    if mqtt_client and mqtt_client.is_connected():
        mqtt_client.publish_sensor_data(result)
    
    # Apply relay logic
    try:
        apply_logic(result)
        logger.debug("Relay control applied")
    except Exception as e:
        logger.error(f"Relay control error: {e}")
    
    return result

if __name__ == "__main__":
    # Initialize alarm system
    alarm_sys = AlarmSystem(config_manager)
    
    # Initialize MQTT client
    mqtt = MQTTClient(config_manager)
    if config_manager.get('mqtt_enabled', False):
        mqtt.connect()
    
    logger.info("🚀 Modbus Reader başlatıldı")
    
    try:
        interval = config_manager.get('interval', 10)
        while True:
            read_sensors(alarm_system=alarm_sys, mqtt_client=mqtt)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Reader stopped by user")
        if mqtt:
            mqtt.disconnect()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if mqtt:
            mqtt.disconnect()