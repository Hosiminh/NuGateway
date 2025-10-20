import json
import os
from typing import Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class GatewayConfig:
    """Gateway configuration settings"""
    gateway_name: str = "nuGateway"
    serial_port: str = "/tmp/ttySIM1"
    baudrate: int = 9600
    interval: int = 10
    data_bits: int = 8
    stop_bits: int = 1
    parity: str = "N"
    location: str = ""
    mac_address: str = ""
    ip_address: str = ""
    
    # Security settings
    enable_auth: bool = False
    api_token: str = ""
    
    # MQTT settings
    mqtt_enabled: bool = False
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic: str = "nugateway/sensors"
    mqtt_username: str = ""
    mqtt_password: str = ""
    
    # Logging settings
    log_level: str = "INFO"
    log_file: str = "nugateway.log"
    enable_data_logging: bool = True
    data_log_file: str = "sensor_data.log"
    
    # Alarm settings
    alarm_enabled: bool = True
    temp_alarm_high: float = 35.0
    temp_alarm_low: float = 5.0
    humidity_alarm_high: float = 85.0
    co2_alarm_high: float = 2000.0
    battery_soc_alarm_low: int = 20

class ConfigManager:
    """Configuration manager with file persistence"""
    
    SETTINGS_FILE = "gateway_settings.json"
    
    def __init__(self):
        self.config = self.load()
    
    def load(self) -> GatewayConfig:
        """Load configuration from file"""
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    return GatewayConfig(**data)
            except Exception as e:
                print(f"⚠️ Config load error: {e}, using defaults")
                return GatewayConfig()
        return GatewayConfig()
    
    def save(self, config: GatewayConfig = None) -> bool:
        """Save configuration to file"""
        try:
            if config:
                self.config = config
            with open(self.SETTINGS_FILE, 'w') as f:
                json.dump(asdict(self.config), f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Config save error: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return getattr(self.config, key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """Set configuration value"""
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            return self.save()
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return asdict(self.config)

# Global config instance
config_manager = ConfigManager()