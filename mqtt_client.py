#!/usr/bin/env python3
"""
NuGateway MQTT Client
Handles MQTT publishing of telemetry data and subscribing to relay control commands
"""

import paho.mqtt.client as mqtt
import json
import logging
import time
import socket
from typing import Dict, Any, Callable, Optional
from datetime import datetime
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class MQTTClient:
    """MQTT client for NuGateway telemetry and control"""
    
    def __init__(self, 
                 broker: str = "broker.nuteknoloji.com",
                 port: int = 1883,
                 device_id: str = None,
                 username: str = "",
                 password: str = "",
                 relay_callback: Callable = None):
        """
        Initialize MQTT client
        
        Args:
            broker: MQTT broker address
            port: MQTT broker port
            device_id: Unique device identifier (defaults to MAC address)
            username: MQTT username (optional)
            password: MQTT password (optional)
            relay_callback: Callback function for relay commands
        """
        self.broker = broker
        self.port = port
        self.device_id = device_id or self._get_device_id()
        self.username = username
        self.password = password
        self.relay_callback = relay_callback
        
        # MQTT topics
        self.topic_telemetry = f"nugateway/{self.device_id}/telemetry"
        self.topic_relay_cmd = f"nugateway/{self.device_id}/command/relay"
        self.topic_upload_cmd = f"nugateway/{self.device_id}/command/upload"
        self.topic_status = f"nugateway/{self.device_id}/status"
        
        # MQTT client
        self.client = mqtt.Client(client_id=f"nugateway_{self.device_id}_{int(time.time())}")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Set credentials if provided
        if username and password:
            self.client.username_pw_set(username, password)
        
        # Connection state
        self.connected = False
        self.lock = Lock()
        
        # Last will and testament
        self.client.will_set(
            self.topic_status,
            payload=json.dumps({"status": "offline", "timestamp": datetime.utcnow().isoformat()}),
            qos=1,
            retain=True
        )
        
        logger.info(f"MQTT client initialized for device: {self.device_id}")
        logger.info(f"Broker: {self.broker}:{self.port}")
    
    def _get_device_id(self) -> str:
        """Get unique device ID from MAC address"""
        try:
            # Get MAC address
            import uuid
            mac = hex(uuid.getnode())[2:].upper()
            # Format as XX:XX:XX:XX:XX:XX
            mac_formatted = ':'.join([mac[i:i+2] for i in range(0, 12, 2)])
            logger.info(f"Device MAC address: {mac_formatted}")
            return mac.replace(':', '')
        except Exception as e:
            logger.warning(f"Could not get MAC address: {e}, using hostname")
            return socket.gethostname()
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"✅ Connected to MQTT broker: {self.broker}:{self.port}")
            
            # Subscribe to command topics
            self.client.subscribe(self.topic_relay_cmd, qos=1)
            self.client.subscribe(self.topic_upload_cmd, qos=1)
            logger.info(f"📡 Subscribed to: {self.topic_relay_cmd}")
            logger.info(f"📡 Subscribed to: {self.topic_upload_cmd}")
            
            # Publish online status
            self._publish_status("online")
        else:
            self.connected = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            logger.error(f"❌ MQTT connection failed: {error_messages.get(rc, f'Unknown error ({rc})')}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"⚠️ Unexpected MQTT disconnection (code: {rc}), will auto-reconnect")
        else:
            logger.info("📴 Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            logger.info(f"📨 Message received on {topic}: {payload}")
            
            # Parse JSON payload
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON payload: {payload}")
                return
            
            # Handle relay commands
            if topic == self.topic_relay_cmd:
                self._handle_relay_command(data)
            
            # Handle upload commands (for future video upload)
            elif topic == self.topic_upload_cmd:
                self._handle_upload_command(data)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _handle_relay_command(self, data: Dict[str, Any]):
        """
        Handle relay control command
        
        Expected format:
        {
            "relay": "load1",  # or "load2", "load3"
            "state": true      # true=ON, false=OFF
        }
        
        or for multiple relays:
        {
            "relays": {
                "load1": true,
                "load2": false,
                "load3": true
            }
        }
        """
        try:
            # Single relay command
            if "relay" in data and "state" in data:
                relay_name = data["relay"]
                state = bool(data["state"])
                
                if relay_name not in ["load1", "load2", "load3"]:
                    logger.warning(f"Invalid relay name: {relay_name}")
                    return
                
                if self.relay_callback:
                    success = self.relay_callback(relay_name, state)
                    logger.info(f"Relay command: {relay_name} = {'ON' if state else 'OFF'} - {'Success' if success else 'Failed'}")
                else:
                    logger.warning("No relay callback configured")
            
            # Multiple relays command
            elif "relays" in data:
                relays = data["relays"]
                for relay_name, state in relays.items():
                    if relay_name in ["load1", "load2", "load3"]:
                        if self.relay_callback:
                            self.relay_callback(relay_name, bool(state))
                    else:
                        logger.warning(f"Invalid relay name: {relay_name}")
            
            else:
                logger.warning(f"Invalid relay command format: {data}")
                
        except Exception as e:
            logger.error(f"Error handling relay command: {e}", exc_info=True)
    
    def _handle_upload_command(self, data: Dict[str, Any]):
        """Handle upload command (placeholder for future video upload)"""
        logger.info(f"Upload command received (not implemented yet): {data}")
        # TODO: Implement video upload functionality
    
    def _publish_status(self, status: str):
        """Publish device status"""
        try:
            payload = {
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "device_id": self.device_id
            }
            self.client.publish(self.topic_status, json.dumps(payload), qos=1, retain=True)
            logger.debug(f"Status published: {status}")
        except Exception as e:
            logger.error(f"Error publishing status: {e}")
    
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            logger.info(f"Connecting to MQTT broker: {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()  # Start background network loop
            
            # Wait for connection (max 5 seconds)
            timeout = 5
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.connected:
                logger.error("Connection timeout")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            if self.connected:
                self._publish_status("offline")
                time.sleep(0.5)  # Give time for message to be sent
            
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def publish_telemetry(self, data: Dict[str, Any]) -> bool:
        """
        Publish telemetry data
        
        Args:
            data: Telemetry data dictionary
            
        Returns:
            True if published successfully
        """
        if not self.connected:
            logger.warning("Not connected to MQTT broker, cannot publish")
            return False
        
        try:
            # Add timestamp and device ID
            payload = {
                "device_id": self.device_id,
                "timestamp": datetime.utcnow().isoformat(),
                **data
            }
            
            # Publish with QoS 1 (at least once delivery)
            result = self.client.publish(
                self.topic_telemetry,
                json.dumps(payload, indent=2),
                qos=1
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"✅ Telemetry published to {self.topic_telemetry}")
                return True
            else:
                logger.error(f"Failed to publish telemetry: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing telemetry: {e}", exc_info=True)
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to MQTT broker"""
        return self.connected


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    def relay_test_callback(relay_name: str, state: bool) -> bool:
        """Test relay callback"""
        print(f"🔌 Relay command received: {relay_name} = {'ON' if state else 'OFF'}")
        return True
    
    # Create MQTT client
    mqtt_client = MQTTClient(
        broker="broker.nuteknoloji.com",
        port=1883,
        relay_callback=relay_test_callback
    )
    
    # Connect
    if mqtt_client.connect():
        print(f"✅ Connected! Device ID: {mqtt_client.device_id}")
        print(f"Publishing to: {mqtt_client.topic_telemetry}")
        print(f"Listening on: {mqtt_client.topic_relay_cmd}")
        
        # Publish test data
        test_data = {
            "BMS": {
                "cell_voltages": [3.446, 3.427, 3.430, 3.424],
                "pack_voltage": 13.72,
                "current": 5.88,
                "soc": 85,
                "soh": 98
            },
            "MPPT": {
                "battery_voltage": 13.92,
                "battery_current": 7.71,
                "pv_voltage": 19.60,
                "pv_current": 5.78
            },
            "ENV": {
                "co2": 510.0,
                "temperature": 16.2
            },
            "LDR": {
                "lux": 0.0
            }
        }
        
        mqtt_client.publish_telemetry(test_data)
        
        # Keep running to receive commands
        print("\n💡 Waiting for relay commands... (Ctrl+C to exit)")
        print("Example command to publish:")
        print(f'  mosquitto_pub -h {mqtt_client.broker} -t {mqtt_client.topic_relay_cmd} -m \'{{"relay":"load1","state":true}}\'')
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  Stopping...")
            mqtt_client.disconnect()
    else:
        print("❌ Failed to connect to MQTT broker")
        sys.exit(1)
