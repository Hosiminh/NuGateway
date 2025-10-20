import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Try to import real GPIO, fallback to mock if not available
try:
    from gpiozero import OutputDevice
    GPIO_AVAILABLE = True
    logger.info("Real GPIO available")
except (ImportError, RuntimeError) as e:
    GPIO_AVAILABLE = False
    logger.warning(f"GPIO not available, using mock: {e}")
    
    # Mock GPIO for development/testing
    class MockOutputDevice:
        def __init__(self, pin, active_high=True, initial_value=False):
            self.pin = pin
            self.active_high = active_high
            self._value = initial_value
            logger.debug(f"Mock relay created on pin {pin}")
        
        @property
        def value(self):
            return self._value
        
        @value.setter
        def value(self, state):
            self._value = state
            status = "ON" if state else "OFF"
            logger.info(f"Mock relay pin {self.pin}: {status}")
        
        def on(self):
            self.value = True
        
        def off(self):
            self.value = False
    
    OutputDevice = MockOutputDevice

# Relay pin configuration (BCM numbering)
RELAY_PINS = {
    "led_light": 5,      # LED lighting control
    "display": 6,         # Display power control
    "load1": 13,          # Generic load 1
    "load2": 19,          # Generic load 2
    "load3": 26,          # Generic load 3
    "load4": 16,          # Generic load 4
    "fan": 20,            # Fan control
    "heater": 21          # Heater control
}

class RelayController:
    """Relay controller with state management"""
    
    def __init__(self):
        self.relays = {}
        self.state = {}
        self._initialize_relays()
    
    def _initialize_relays(self):
        """Initialize all relay outputs"""
        for name, pin in RELAY_PINS.items():
            try:
                self.relays[name] = OutputDevice(
                    pin, 
                    active_high=True, 
                    initial_value=False
                )
                self.state[name] = False
                logger.info(f"Relay '{name}' initialized on pin {pin}")
            except Exception as e:
                logger.error(f"Failed to initialize relay '{name}' on pin {pin}: {e}")
    
    def set_relay(self, name: str, state: bool) -> bool:
        """Set relay state"""
        if name not in self.relays:
            logger.warning(f"Unknown relay: {name}")
            return False
        
        try:
            self.relays[name].value = state
            self.state[name] = state
            logger.debug(f"Relay '{name}': {'ON' if state else 'OFF'}")
            return True
        except Exception as e:
            logger.error(f"Failed to set relay '{name}': {e}")
            return False
    
    def get_relay(self, name: str) -> bool:
        """Get relay state"""
        return self.state.get(name, False)
    
    def get_all_states(self) -> Dict[str, bool]:
        """Get all relay states"""
        return self.state.copy()
    
    def toggle_relay(self, name: str) -> bool:
        """Toggle relay state"""
        current = self.get_relay(name)
        return self.set_relay(name, not current)
    
    def all_off(self):
        """Turn off all relays"""
        for name in self.relays.keys():
            self.set_relay(name, False)
        logger.info("All relays turned OFF")
    
    def all_on(self):
        """Turn on all relays"""
        for name in self.relays.keys():
            self.set_relay(name, True)
        logger.info("All relays turned ON")

# Global relay controller instance
relay_controller = RelayController()

def set_relay(name: str, state: bool) -> bool:
    """Set relay state (compatibility function)"""
    return relay_controller.set_relay(name, state)

def apply_logic(data: Dict[str, Any]):
    """Apply automation logic based on sensor data"""
    
    # LED light control based on ambient light
    is_dark = data.get("is_dark", False)
    relay_controller.set_relay("led_light", is_dark)
    
    # Display control based on motion detection
    display_on = data.get("display_should_be_on", False)
    relay_controller.set_relay("display", display_on)
    
    # Load control based on battery level
    low_power = data.get("bms_low_power_mode", False)
    relay_controller.set_relay("load1", not low_power)
    relay_controller.set_relay("load2", not low_power)
    
    # Fan control based on temperature
    temp = data.get("temperature", 20.0)
    if temp > 30.0:
        relay_controller.set_relay("fan", True)
    elif temp < 25.0:
        relay_controller.set_relay("fan", False)
    
    # Heater control based on temperature
    if temp < 15.0:
        relay_controller.set_relay("heater", True)
    elif temp > 20.0:
        relay_controller.set_relay("heater", False)
    
    logger.debug(f"Automation logic applied: dark={is_dark}, temp={temp}°C, low_power={low_power}")

def get_relay_states() -> Dict[str, bool]:
    """Get current state of all relays"""
    return relay_controller.get_all_states()

def manual_control(name: str, state: bool) -> bool:
    """Manual relay control (overrides automation)"""
    logger.info(f"Manual control: {name} = {'ON' if state else 'OFF'}")
    return relay_controller.set_relay(name, state)

# Cleanup function
def cleanup():
    """Turn off all relays on exit"""
    logger.info("Cleaning up relays...")
    relay_controller.all_off()

if __name__ == "__main__":
    # Test relay controller
    logging.basicConfig(level=logging.INFO)
    
    print("Testing relay controller...")
    print(f"Available relays: {list(RELAY_PINS.keys())}")
    
    # Test each relay
    for name in RELAY_PINS.keys():
        print(f"\nTesting {name}...")
        relay_controller.set_relay(name, True)
        import time
        time.sleep(0.5)
        relay_controller.set_relay(name, False)
        time.sleep(0.5)
    
    print("\nRelay states:", relay_controller.get_all_states())
    cleanup()