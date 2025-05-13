from gpiozero import OutputDevice

RELAY_PINS = {
    "led_light": 5,
    "display": 6,
    "load1": 13,
    "load2": 19
}

RELAYS = {name: OutputDevice(pin, active_high=True, initial_value=False) for name, pin in RELAY_PINS.items()}

def set_relay(name, state):
    if name in RELAYS:
        RELAYS[name].value = state

def apply_logic(data):
    set_relay("led_light", data.get("is_dark", False))
    set_relay("display", data.get("display_should_be_on", False))
    low_power = data.get("bms_low_power_mode", False)
    set_relay("load1", not low_power)
    set_relay("load2", not low_power)
