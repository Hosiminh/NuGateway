#!/usr/bin/env python3
import serial
import sys

if len(sys.argv) < 2:
    print("Kullanım: python3 test_modbus.py [PORT]")
    print("Örnek: python3 test_modbus.py /dev/ttyUSB0")
    sys.exit(1)

port = sys.argv[1]
packet = bytes.fromhex('0104304600 01DF1F')

ser = serial.Serial(port, 9600, timeout=1)
ser.write(packet)
response = ser.read(100)
print(f"Cevap: {response.hex() if response else 'YOK'}")
ser.close()
