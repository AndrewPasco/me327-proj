import asyncio
from bleak import BleakClient
from bleak import BleakScanner

DEVICE_UUID = "33626148-5969-F52D-B23E-A3540B156C24"

DEVICE_MAC = "EF:6C:92:99:B5:79"

# The UUID of the characteristics
# note that tx is the devices tx, so will be recieving here
TX_UUID = "62c3cf89-247b-4c0f-a70d-651080844608"
RX_UUID = "62c3cf89-247b-4c0f-a70d-651080844609"

# 1. Define the callback function that "hears" the data
def notification_handler(characteristic, data):
    """
    characteristic: The BleakGATTCharacteristic object
    data: bytearray containing the received data
    """
    print(f"Received from {characteristic.description}: {data}")

async def main(address):
    # 2. Connect to the device
    # stop_event = asyncio.Event()


    # async with BleakScanner(callback) as scanner:
    #     await asyncio.sleep(30.0)

    async with BleakClient(DEVICE_ADDRESS) as client: # instead of DEVICE_UUID
        print(f"Connected: {client.is_connected}")

        # 3. Start listening (subscribing to notifications)
        await client.start_notify(TX_UUID, notification_handler)
        
        # 4. Keep the script running to continue listening
        print("Listening for 30 seconds...")
        await asyncio.sleep(30.0)
        
        # 5. Stop listening before disconnecting
        await client.stop_notify(TX_UUID)

def callback(device, advertising_data):
    # TODO: do something with incoming data
    if device.name == "Argon Test":
        print(f"found: {device.name}")


if __name__ == "__main__":
    # Replace with your device's MAC address or UUID
    DEVICE_ADDRESS = "EF:6C:92:99:B5:79" 
    asyncio.run(main(DEVICE_ADDRESS))
