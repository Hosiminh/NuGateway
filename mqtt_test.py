#!/usr/bin/env python3
"""
MQTT Test Script
Test publishing relay commands to NuGateway
"""

import paho.mqtt.client as mqtt
import json
import time
import sys

# Configuration
BROKER = "broker.nuteknoloji.com"
PORT = 1883
DEVICE_ID = "YOUR_DEVICE_ID"  # Replace with your actual device ID

# Topics
TOPIC_RELAY_CMD = f"nugateway/{DEVICE_ID}/command/relay"
TOPIC_TELEMETRY = f"nugateway/{DEVICE_ID}/telemetry"
TOPIC_STATUS = f"nugateway/{DEVICE_ID}/status"


def on_connect(client, userdata, flags, rc):
    """Callback when connected"""
    if rc == 0:
        print(f"✅ Connected to MQTT broker: {BROKER}:{PORT}")
        # Subscribe to telemetry to see responses
        client.subscribe(TOPIC_TELEMETRY)
        client.subscribe(TOPIC_STATUS)
        print(f"📡 Subscribed to {TOPIC_TELEMETRY}")
        print(f"📡 Subscribed to {TOPIC_STATUS}")
    else:
        print(f"❌ Connection failed with code {rc}")


def on_message(client, userdata, msg):
    """Callback when message received"""
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        print(f"\n📨 Message on {msg.topic}:")
        print(json.dumps(payload, indent=2))
    except:
        print(f"\n📨 Message on {msg.topic}: {msg.payload.decode('utf-8')}")


def send_relay_command(client, relay_name, state):
    """Send relay control command"""
    command = {
        "relay": relay_name,
        "state": state
    }
    
    print(f"\n🔌 Sending command: {relay_name} = {'ON' if state else 'OFF'}")
    result = client.publish(TOPIC_RELAY_CMD, json.dumps(command), qos=1)
    
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print("✅ Command sent successfully")
    else:
        print(f"❌ Failed to send command: {result.rc}")


def send_multiple_relay_command(client, relays):
    """Send multiple relay control command"""
    command = {
        "relays": relays
    }
    
    print(f"\n🔌 Sending multiple relay command:")
    for relay, state in relays.items():
        print(f"   {relay} = {'ON' if state else 'OFF'}")
    
    result = client.publish(TOPIC_RELAY_CMD, json.dumps(command), qos=1)
    
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print("✅ Command sent successfully")
    else:
        print(f"❌ Failed to send command: {result.rc}")


def main():
    """Main function"""
    global DEVICE_ID
    
    # Get device ID from command line or prompt
    if len(sys.argv) > 1:
        DEVICE_ID = sys.argv[1]
    else:
        print("Enter device ID (or press Enter to use default):")
        user_input = input("> ").strip()
        if user_input:
            DEVICE_ID = user_input
    
    print("=" * 60)
    print("🧪 NuGateway MQTT Test Client")
    print("=" * 60)
    print(f"Broker: {BROKER}:{PORT}")
    print(f"Device ID: {DEVICE_ID}")
    print(f"Command Topic: {TOPIC_RELAY_CMD}")
    print("=" * 60)
    
    # Create MQTT client
    client = mqtt.Client(client_id=f"test_client_{int(time.time())}")
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect
    try:
        print(f"\n🔄 Connecting to {BROKER}:{PORT}...")
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()
        
        # Wait for connection
        time.sleep(2)
        
        # Interactive menu
        while True:
            print("\n" + "=" * 60)
            print("Select an option:")
            print("1. Turn ON relay load1")
            print("2. Turn OFF relay load1")
            print("3. Turn ON relay load2")
            print("4. Turn OFF relay load2")
            print("5. Turn ON relay load3")
            print("6. Turn OFF relay load3")
            print("7. Turn ON all relays")
            print("8. Turn OFF all relays")
            print("9. Custom command")
            print("0. Exit")
            print("=" * 60)
            
            choice = input("Enter choice: ").strip()
            
            if choice == '1':
                send_relay_command(client, "load1", True)
            elif choice == '2':
                send_relay_command(client, "load1", False)
            elif choice == '3':
                send_relay_command(client, "load2", True)
            elif choice == '4':
                send_relay_command(client, "load2", False)
            elif choice == '5':
                send_relay_command(client, "load3", True)
            elif choice == '6':
                send_relay_command(client, "load3", False)
            elif choice == '7':
                send_multiple_relay_command(client, {
                    "load1": True,
                    "load2": True,
                    "load3": True
                })
            elif choice == '8':
                send_multiple_relay_command(client, {
                    "load1": False,
                    "load2": False,
                    "load3": False
                })
            elif choice == '9':
                relay = input("Enter relay name (load1/load2/load3): ").strip()
                state_input = input("Enter state (on/off): ").strip().lower()
                state = state_input == 'on'
                send_relay_command(client, relay, state)
            elif choice == '0':
                break
            else:
                print("❌ Invalid choice")
            
            time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        print("\n🔄 Disconnecting...")
        client.loop_stop()
        client.disconnect()
        print("👋 Goodbye!")


if __name__ == '__main__':
    main()
