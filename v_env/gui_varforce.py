# written by Ashlynn as the start of the GUI for the project. 
# This is a simple visualization of the user's heading and the threat location, and it sends motor commands based on the relative angle between the user and the threat. 
# The user can left click to set the threat location and use the A/D keys to rotate their heading. Use right click to clear all threats.
# This script supports multiple threats and variable force based on the distance to the threat.

# runs on python 3.11 with pygame, pyserial, numpy, scipy, filterpy, bleak installed.

import pygame
import math
# import serial
import time
from collections import defaultdict
# BT imports
import asyncio
from bleak import BleakClient
import threading

# ------------------
# CONFIG
# ------------------

WIDTH = 800
HEIGHT = 800

CENTER = (WIDTH // 2, HEIGHT // 2)

THREATS = []

user_heading_deg = 0
latest_heading = 0

NUM_MOTORS = 8
SECTOR_SIZE = 360 / NUM_MOTORS

# For serial
# ser = serial.Serial("/dev/ttyUSB0", 115200)

# For BLE
# BLE_ADDRESS = "XX:XX:XX:XX:XX:XX"  # replace with device's MAC address
# BLE_CHARACTERISTIC_UUID = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"  # replace with characteristic UUID

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

def normalize_angle(angle):
    return angle % 360

def angle_to_motor(angle):

    sector = round(
        angle / SECTOR_SIZE
    ) % NUM_MOTORS

    return sector

def compute_motor_votes(threats):
    "If there are multiple threats, this function computes "
    "how many threats fall into each motor's sector, allowing for multiple motors to activate simultaneously if there are multiple threats in different directions. "
    "It also weights the votes based on the distance to the threat, so closer threats have a stronger influence on the motor activation."
    votes = [0.0] * NUM_MOTORS

    for (tx, ty) in threats:

        dx = tx - CENTER[0]
        dy = ty - CENTER[1]

        dist = math.sqrt(dx*dx + dy*dy)

        # avoid division by zero
        weight = 1.0 / (dist + 1e-6)

        world_angle = math.degrees(math.atan2(dx, dy))
        relative = normalize_angle(world_angle - user_heading_deg)

        motor = angle_to_motor(relative)

        votes[motor] += weight

    return votes

def send_motor_command(votes):
    max_v = max(votes, default=0.0)

    if max_v == 0:
        print("TX: no active threats\n")
        return

    normalized = [v / max_v for v in votes]

    active = [
        f"{i}:{normalized[i]:.2f}"
        for i in range(len(normalized))
        if normalized[i] > 0.05
    ]

    msg = ",".join(active) + "\n"

    print("TX:", msg)

    # added for hardware testing - sends all active motors in one message, separated by commas. For example, if motors 0, 3, and 5 are active, it sends "0,3,5\n"
    # ser.write(msg.encode())

def handle_ble_data(sender, data):
    global latest_heading

    try:
        msg = data.decode().strip()

        # assumes "YAW,127.4" is what the BLE device sends, where 127.4 is the heading in degrees
        if "YAW" in msg:
            latest_heading = float(msg.split(",")[1])

        else:
            latest_heading = float(msg)

    except:
        pass

async def ble_loop():
    global latest_heading

    async with BleakClient(BLE_ADDRESS) as client:
        print("Connected to IMU BLE")

        await client.start_notify(BLE_CHARACTERISTIC_UUID, handle_ble_data)

        while True:
            await asyncio.sleep(0.01)

# running in a background thread
def start_ble():
    asyncio.run(ble_loop())
# uncomment when using the BLE functionality
# ble_thread = threading.Thread(target=start_ble, daemon=True)
# ble_thread.start()

running = True

while running:

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # left click to add threat   
                THREATS.append(list(event.pos))
            if event.button == 3:  # right click to clear threats
                THREATS.clear()

    # replace the keys with the following line to use BLE heading instead of keyboard input
    # user_heading_deg = latest_heading

    # ------- KEYBOARD ------------
    keys = pygame.key.get_pressed()

    if keys[pygame.K_a]:
        user_heading_deg += 2

    if keys[pygame.K_d]:
        user_heading_deg -= 2
    # ----------- KEYBOARD ----------

    votes = compute_motor_votes(THREATS)
    send_motor_command(votes)

    # ------------------
    # DRAW
    # ------------------

    screen.fill((20, 20, 20))

    # user
    pygame.draw.circle(
        screen,
        (255,255,255),
        CENTER,
        20
    )

    # heading arrow
    hx = CENTER[0] + 60*math.sin(
        math.radians(
            user_heading_deg
        )
    )

    hy = CENTER[1] - 60*math.cos(
        math.radians(
            user_heading_deg
        )
    )

    pygame.draw.line(
        screen,
        (0,255,0),
        CENTER,
        (hx, hy),
        4
    )

    # threat
    for (tx, ty) in THREATS:
        pygame.draw.circle(screen, (255,0,0), (tx, ty), 10)

    pygame.display.flip()

    clock.tick(30)

pygame.quit()
