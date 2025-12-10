import serial
import time

PORT = "/dev/ttyUSB0"
BAUDRATE = 9600

# -------------------------------------------------
# DENENECEK KOMUTLAR (00 00 = OFF / alarm kapatma)
# -------------------------------------------------
commands = {
    "co2_off_div2_addr":     "7B 10 00 18 00 01 02 00 00 B7 61",

    "temphum_off_doc_addr":  "7B 06 00 24 00 00 B8 21",
    "temphum_off_div2_addr": "7B 06 00 12 00 00 38 21",
}

def send(ser, name, cmd):
    print(f"\n>> {name}: {cmd}")
    ser.write(bytes.fromhex(cmd))
    time.sleep(0.20)
    resp = ser.read_all()
    if resp:
        print("<<", resp.hex())
    else:
        print("<< CEVAP YOK")

def main():
    ser = serial.Serial(PORT, BAUDRATE, timeout=0.5)
    print("Test başlıyor...\n")

    for name, cmd in commands.items():
        send(ser, name, cmd)
        time.sleep(0.5)

    ser.close()
    print("\nBitti.")

if __name__ == "__main__":
    main()
