import logging
import json
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt
from threading import Thread

class MQTTClient:
    """MQTT client for IoT integration"""
    
    def __init__(self, config):
        self.config = config
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        
        if config.get('mqtt_enabled', False):
            self._initialize()
    
    def _initialize(self):
        """Initialize MQTT client"""
        try:
            self.client = mqtt.Client(client_id=f"nugateway_{self.config.get('gateway_name', 'default')}")
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Set credentials if provided
            username = self.config.get('mqtt_username', '')
            password = self.config.get('mqtt_password', '')
            if username and password:
                self.client.username_pw_set(username, password)
            
            logging.info("MQTT client initialized")
            
        except Exception as e:
            logging.error(f"MQTT initialization failed: {e}")
    
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        if not self.client:
            return False
        
        try:
            broker = self.config.get('mqtt_broker', 'localhost')
            port = self.config.get('mqtt_port', 1883)
            
            self.client.connect(broker, port, keepalive=60)
            
            # Start network loop in background
            self.client.loop_start()
            
            logging.info(f"Connecting to MQTT broker {broker}:{port}")
            return True
            
        except Exception as e:
            logging.error(f"MQTT connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logging.info("MQTT disconnected")
    
    def publish_sensor_data(self, data: Dict[str, Any]) -> bool:
        """Publish sensor data to MQTT topic"""
        if not self.connected or not self.client:
            return False
        
        try:
            topic = self.config.get('mqtt_topic', 'nugateway/sensors')
            payload = json.dumps(data)
            
            result = self.client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.debug(f"Published to {topic}")
                return True
            else:
                logging.warning(f"Publish failed with code {result.rc}")
                return False
                
        except Exception as e:
            logging.error(f"MQTT publish error: {e}")
            return False
    
    def publish_alarm(self, alarm: Dict[str, Any]) -> bool:
        """Publish alarm to MQTT"""
        if not self.connected or not self.client:
            return False
        
        try:
            topic = f"{self.config.get('mqtt_topic', 'nugateway/sensors')}/alarms"
            payload = json.dumps(alarm)
            
            result = self.client.publish(topic, payload, qos=2)  # QoS 2 for alarms
            return result.rc == mqtt.MQTT_ERR_SUCCESS
            
        except Exception as e:
            logging.error(f"MQTT alarm publish error: {e}")
            return False
    
    def subscribe_control(self, callback):
        """Subscribe to control topic for remote commands"""
        if not self.connected or not self.client:
            return False
        
        try:
            control_topic = f"{self.config.get('mqtt_topic', 'nugateway/sensors')}/control"
            self.client.subscribe(control_topic, qos=1)
            self.control_callback = callback
            logging.info(f"Subscribed to {control_topic}")
            return True
            
        except Exception as e:
            logging.error(f"MQTT subscribe error: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for connection"""
        if rc == 0:
            self.connected = True
            logging.info("MQTT connected successfully")
        else:
            self.connected = False
            logging.error(f"MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for disconnection"""
        self.connected = False
        if rc != 0:
            logging.warning(f"MQTT unexpected disconnect: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback for incoming messages"""
        try:
            payload = json.loads(msg.payload.decode())
            logging.info(f"MQTT message received: {msg.topic}")
            
            if hasattr(self, 'control_callback'):
                self.control_callback(msg.topic, payload)
                
        except Exception as e:
            logging.error(f"MQTT message processing error: {e}")
    
    def is_connected(self) -> bool:
        """Check if MQTT is connected"""
        return self.connected