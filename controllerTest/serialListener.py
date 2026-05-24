import serial
import time

PORT = "/dev/tty.usbmodem101"   # change this
BAUD = 9600

ser = serial.Serial(PORT, BAUD, timeout=1)

# let the port settle after opening
time.sleep(2)

print(f"Listening on {PORT} at {BAUD} baud...\n")

while True:
    if ser.in_waiting:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        print(line)