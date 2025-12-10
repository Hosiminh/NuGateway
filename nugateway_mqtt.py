#!/usr/bin/env python3
"""
NuGateway Main Script with MQTT Integration
Reads Modbus data and publishes to MQTT broker
Listens for relay control commands from MQTT
"""

import sys
import os
import time
import json
import logging
import signal
from datetime import datetime
from typing import Dict, Any

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import local modules
try:
    from modbus_reader import ModbusReader
    from mqtt_client import MQTTClient
    from relay_control import relay_controller, manual_control
    from config import config_manager
    from logger import setup_logging
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure all required modules are in the same directory")
    sys.exit(1)


# Setup logging
setup_logging(
    log_level=config_manager.get('log_level', 'INFO'),
    log_file=config_manager.get('log_file', 'nugateway.log')
)
logger = logging.getLogger(__name__)


class NuGatewayMQTT:
    """Main NuGateway application with MQTT support"""
    
    def __init__(self):
        self.running = False
        self.modbus_reader = None
        self.mqtt_client = None
        
        # Configuration
        self.serial_port = config_manager.get('serial_port', '/dev/ttyUSB0')
        self.baudrate = config_manager.get('baudrate', 9600)
        self.publish_interval = 300  # 5 minutes in seconds
        
        # MQTT configuration
        self.mqtt_broker = config_manager.get('mqtt_broker', 'broker.nuteknoloji.com')
        self.mqtt_port = config_manager.get('mqtt_port', 1883)
        self.mqtt_username = config_manager.get('mqtt_username', '')
        self.mqtt_password = config_manager.get('mqtt_password', '')
        
        logger.info("=" * 60)
        logger.info("🚀 NuGateway MQTT Service")
        logger.info("=" * 60)
        logger.info(f"Serial Port: {self.serial_port}")
        logger.info(f"Baud Rate: {self.baudrate}")
        logger.info(f"MQTT Broker: {self.mqtt_broker}:{self.mqtt_port}")
        logger.info(f"Publish Interval: {self.publish_interval} seconds ({self.publish_interval//60} minutes)")
        logger.info("=" * 60)
    
    def relay_command_handler(self, relay_name: str, state: bool) -> bool:
        """
        Handle relay control commands from MQTT
        
        Args:
            relay_name: Name of relay (load1, load2, load3)
            state: True for ON, False for OFF
            
        Returns:
            True if successful
        """
        try:
            success = manual_control(relay_name, state)
            if success:
                logger.info(f"✅ Relay '{relay_name}' set to {'ON' if state else 'OFF'}")
            else:
                logger.error(f"❌ Failed to control relay '{relay_name}'")
            return success
        except Exception as e:
            logger.error(f"Error controlling relay: {e}")
            return False
    
    def format_telemetry_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format raw Modbus data into structured telemetry format
        
        Args:
            raw_data: Raw data from Modbus reader
            
        Returns:
            Formatted telemetry data
        """
        try:
            # Get relay states
            relay_states = relay_controller.get_all_states()
            
            # Format telemetry data
            telemetry = {
                "Asset": {
                    "schema_version": "1.0",
                    "device_serial": f"NU-GW-{self.mqtt_client.device_id}" if self.mqtt_client else "UNKNOWN",
                    "manufacturer_id": "NuTech",
                    "firmware_version": "1.0.0",
                    "location_id": config_manager.get('location', 'UNKNOWN'),
                },
                
                "BMS": {
                    "cell_voltages": [
                        raw_data.get('bms_cell_1_voltage', 0.0),
                        raw_data.get('bms_cell_2_voltage', 0.0),
                        raw_data.get('bms_cell_3_voltage', 0.0),
                        raw_data.get('bms_cell_4_voltage', 0.0),
                    ],
                    "pack_voltage_V": raw_data.get('bms_battery_voltage', 0.0),
                    "current_A": raw_data.get('bms_battery_current', 0.0),
                    "soc_pct": raw_data.get('bms_battery_soc', 0),
                    "soh_pct": raw_data.get('bms_battery_soh', 0),
                    "temperature_C": raw_data.get('bms_temperature', 0.0),
                    "charge_mos": raw_data.get('bms_charge_mos_status', 'UNKNOWN'),
                    "discharge_mos": raw_data.get('bms_discharge_mos_status', 'UNKNOWN'),
                },
                
                "MPPT": {
                    "battery_voltage_V": raw_data.get('mppt_battery_voltage', 0.0),
                    "battery_current_A": raw_data.get('mppt_battery_current', 0.0),
                    "pv_voltage_V": raw_data.get('mppt_pv_voltage', 0.0),
                    "pv_current_A": raw_data.get('mppt_pv_current', 0.0),
                    "battery_power_W": raw_data.get('mppt_battery_voltage', 0.0) * raw_data.get('mppt_battery_current', 0.0),
                    "pv_power_W": raw_data.get('mppt_pv_voltage', 0.0) * raw_data.get('mppt_pv_current', 0.0),
                },
                
                "Sensors": {
                    "ENV": {
                        "co2_ppm": raw_data.get('env_co2', 0.0),
                        "temperature_C": raw_data.get('env_temperature', 0.0),
                        "humidity_pct": raw_data.get('env_humidity', 0.0),
                    },
                    "LDR": {
                        "ambient_light_lux": raw_data.get('ldr_lux', 0.0),
                    },
                    "PIR": {
                        "motion_detected": raw_data.get('pir_motion_detected', False),
                    }
                },
                
                "Relays": {
                    "load1": relay_states.get('load1', False),
                    "load2": relay_states.get('load2', False),
                    "load3": relay_states.get('load3', False),
                },
                
                "Timestamp": {
                    "gateway": datetime.utcnow().isoformat() + "Z",
                    "reading": datetime.now().isoformat(),
                }
            }
            
            return telemetry
            
        except Exception as e:
            logger.error(f"Error formatting telemetry data: {e}", exc_info=True)
            return {}
    
    def initialize(self) -> bool:
        """Initialize Modbus reader and MQTT client"""
        try:
            # Initialize Modbus reader
            logger.info("🔧 Initializing Modbus reader...")
            self.modbus_reader = ModbusReader(
                port=self.serial_port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            
            if not self.modbus_reader.connect():
                logger.error("❌ Failed to connect to Modbus devices")
                return False
            
            logger.info("✅ Modbus reader connected")
            
            # Initialize MQTT client
            logger.info("🔧 Initializing MQTT client...")
            self.mqtt_client = MQTTClient(
                broker=self.mqtt_broker,
                port=self.mqtt_port,
                username=self.mqtt_username,
                password=self.mqtt_password,
                relay_callback=self.relay_command_handler
            )
            
            if not self.mqtt_client.connect():
                logger.error("❌ Failed to connect to MQTT broker")
                return False
            
            logger.info("✅ MQTT client connected")
            logger.info(f"📡 Publishing to: {self.mqtt_client.topic_telemetry}")
            logger.info(f"📡 Listening on: {self.mqtt_client.topic_relay_cmd}")
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization error: {e}", exc_info=True)
            return False
    
    def read_and_publish(self):
        """Read Modbus data and publish to MQTT"""
        try:
            logger.info("=" * 60)
            logger.info(f"📡 Reading Modbus devices... [{datetime.now().strftime('%H:%M:%S')}]")
            
            # Read all Modbus devices
            raw_data = self.modbus_reader.read_all_devices()
            
            if not raw_data:
                logger.warning("⚠️  No data received from Modbus devices")
                return False
            
            logger.info(f"✅ Read {len(raw_data)} parameters from Modbus devices")
            
            # Format telemetry data
            telemetry = self.format_telemetry_data(raw_data)
            
            # Save to local JSON file (for backup)
            try:
                with open('telemetry_data.json', 'w') as f:
                    json.dump(telemetry, f, indent=2)
                logger.debug("💾 Telemetry saved to local file")
            except Exception as e:
                logger.warning(f"Failed to save local telemetry: {e}")
            
            # Publish to MQTT
            if self.mqtt_client and self.mqtt_client.is_connected():
                success = self.mqtt_client.publish_telemetry(telemetry)
                if success:
                    logger.info("✅ Telemetry published to MQTT broker")
                else:
                    logger.error("❌ Failed to publish telemetry")
                return success
            else:
                logger.warning("⚠️  MQTT client not connected, skipping publish")
                return False
                
        except Exception as e:
            logger.error(f"Error in read_and_publish: {e}", exc_info=True)
            return False
    
    def run(self):
        """Main run loop"""
        self.running = True
        last_publish_time = 0
        
        logger.info("=" * 60)
        logger.info("🚀 Starting main loop...")
        logger.info(f"⏱️  Will publish every {self.publish_interval} seconds")
        logger.info("   Press Ctrl+C to stop")
        logger.info("=" * 60)
        
        try:
            while self.running:
                current_time = time.time()
                
                # Check if it's time to publish
                if current_time - last_publish_time >= self.publish_interval:
                    self.read_and_publish()
                    last_publish_time = current_time
                    
                    # Show next publish time
                    next_publish = self.publish_interval - (time.time() - last_publish_time)
                    logger.info(f"⏱️  Next publish in {int(next_publish)} seconds")
                
                # Sleep for a bit (check more frequently for shutdown)
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("\n⏹️  Stopping NuGateway (user interrupt)...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        logger.info("🔄 Shutting down...")
        self.running = False
        
        # Disconnect MQTT
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
                logger.info("✅ MQTT client disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting MQTT: {e}")
        
        # Disconnect Modbus
        if self.modbus_reader:
            try:
                self.modbus_reader.disconnect()
                logger.info("✅ Modbus reader disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting Modbus: {e}")
        
        # Turn off all relays
        try:
            relay_controller.all_off()
            logger.info("✅ All relays turned OFF")
        except Exception as e:
            logger.error(f"Error turning off relays: {e}")
        
        logger.info("=" * 60)
        logger.info("👋 NuGateway stopped")
        logger.info("=" * 60)


def main():
    """Main entry point"""
    # Create application
    app = NuGatewayMQTT()
    
    # Setup signal handlers for clean shutdown
    def signal_handler(sig, frame):
        logger.info("\n⚠️  Signal received, shutting down...")
        app.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize
    if not app.initialize():
        logger.error("❌ Initialization failed, exiting...")
        sys.exit(1)
    
    # Run
    app.run()
    
    sys.exit(0)


if __name__ == '__main__':
    main()
