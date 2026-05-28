# This visualization shows the user heading and multiple threat locations.
#
# LEFT CLICK:
#   - click empty space -> create threat
#   - click and hold on existing threat -> drag threat
#
# RIGHT CLICK:
#   - click threat -> remove only that threat
#   - click empty space -> remove all threats
#
# Threat data is transmitted as:
#   threat_id,x,y,z
#
# Coordinate system:
#   user position = (0,0,0)
#   +x = right
#   +y = up (as seen on screen)
#
# z values:
#   z = 0   -> active threat
#   z = -1  -> threat removed
#
# Threat IDs are unique and never reused.
#
# runs on python 3.11 with: pygame, pyserial, numpy, scipy, filterpy, bleak, bluetooth, bluez, bluez-tools

import pygame
import math
import asyncio
from bleak import BleakScanner, BleakClient
import threading

# ------------------
# CONFIG
# ------------------

WIDTH = 800
HEIGHT = 800

CENTER = (WIDTH // 2, HEIGHT // 2)

THREATS = []
NEXT_THREAT_ID = 0

# constants for sector visualization
NUM_MOTORS = 8
SECTOR_SIZE = 360.0 / NUM_MOTORS

SECTOR_INNER_RADIUS = 40
SECTOR_OUTER_RADIUS = 390

drag_index = None

latest_heading = 0
latest_quaternion = [1.0, 0.0, 0.0, 0.0]
user_heading_deg = 0
heading_lock = threading.Lock()
last_sent_heading = None
last_printed_heading = None

BLE_ADDRESS = None
ble_client = None
ble_loop_ref = None
BLE_RX_UUID = "62c3cf89-247b-4c0f-a70d-651080844608"   # board sends this signal which is recieved by my computer
BLE_TX_UUID = "62c3cf89-247b-4c0f-a70d-651080844609"   # my computer sends this signal which is received by the board 

# ------------------
# PYGAME INIT
# ------------------

pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Threat Visualization")

clock = pygame.time.Clock()

# ------------------
# THREAT TX
# ------------------

def send_threat_data(threats):

    # if len(threats) == 0:
    #     final_msg = "CLEAR"
    #     print("TX:", final_msg)
    #     send_ble_message(final_msg + "\n")
    #     return
    if len(threats) == 0:
        return

    messages = []

    for threat in threats:

        threat_id = threat["id"]

        tx = threat["global_x"]
        ty = threat["global_y"]

        # convert to user-centered coordinates
        global_x = tx - CENTER[0]

        # invert pygame Y axis
        global_y = CENTER[1] - ty

        z = 0

        msg = f"{threat_id},{global_x},{global_y},{z}"

        messages.append(msg)

    final_msg = ";".join(messages)

    print("TX:", final_msg)
    send_ble_message(final_msg + "\n")

def send_single_threat(threat):

    threat_id = threat["id"]

    tx = threat["global_x"]
    ty = threat["global_y"]

    global_x = tx - CENTER[0]
    global_y = CENTER[1] - ty

    msg = f"{threat_id},{global_x},{global_y},0"

    print("TX:", msg)
    send_ble_message(msg + "\n")

def send_move_threat(threat):
    threat_id = threat["id"]

    tx = threat["global_x"]
    ty = threat["global_y"]

    global_x = tx - CENTER[0]
    global_y = CENTER[1] - ty

    msg = f"{threat_id},{global_x},{global_y},0"

    print("TX:", msg)
    send_ble_message(msg + "\n")

def quaternion_to_yaw_deg(w, x, y, z):

    # standard quaternion -> yaw conversion

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)

    yaw_rad = math.atan2(siny_cosp, cosy_cosp)

    yaw_deg = math.degrees(yaw_rad)

    return yaw_deg

# ------------------
# SECTOR VISUALIZATION
# ------------------
def get_threat_relative_angle(threat, heading_deg):
    """
    Returns threat angle relative to the user's heading.

    0 deg   = straight ahead
    90 deg  = right
    180 deg = behind
    270 deg = left
    """

    dx = threat["global_x"] - CENTER[0]

    # convert pygame coordinates to standard coordinates
    dy = CENTER[1] - threat["global_y"]

    world_angle = math.degrees(
        math.atan2(dx, dy)
    )

    relative_angle = (
        world_angle - heading_deg
    ) % 360

    return relative_angle

def get_threat_sector(threat, heading_deg):

    angle = get_threat_relative_angle(threat, heading_deg)

    angle = (angle + SECTOR_SIZE / 2) % 360

    return int(angle // SECTOR_SIZE)

def get_active_sectors(threats, heading_deg):

    active_sectors = set()

    for threat in threats:

        sector = get_threat_sector(
            threat,
            heading_deg
        )

        active_sectors.add(sector)

    return active_sectors

def draw_sector(
    screen,
    center,
    start_angle_deg,
    end_angle_deg,
    inner_radius,
    outer_radius,
    color,
    border_color=(120, 120, 120),
    border_width=2,
    resolution=20
):

    points = []

    #
    # outer arc
    #
    for i in range(resolution + 1):

        frac = i / resolution

        angle = (
            start_angle_deg
            + frac * (end_angle_deg - start_angle_deg)
        )

        x = center[0] + outer_radius * math.sin(
            math.radians(angle)
        )

        y = center[1] - outer_radius * math.cos(
            math.radians(angle)
        )

        points.append((x, y))

    #
    # inner arc (reverse direction)
    #
    for i in range(resolution, -1, -1):

        frac = i / resolution

        angle = (
            start_angle_deg
            + frac * (end_angle_deg - start_angle_deg)
        )

        x = center[0] + inner_radius * math.sin(
            math.radians(angle)
        )

        y = center[1] - inner_radius * math.cos(
            math.radians(angle)
        )

        points.append((x, y))

    pygame.draw.polygon(
        screen,
        color,
        points
    )

    pygame.draw.polygon(
        screen,
        border_color,
        points,
        border_width
    )

def draw_sector_map(screen, center, heading_deg, active_sectors ):

    for sector in range(NUM_MOTORS):

        start_angle = (heading_deg - SECTOR_SIZE/2 + sector * SECTOR_SIZE)

        end_angle = (heading_deg - SECTOR_SIZE/2 + (sector + 1) * SECTOR_SIZE)

        if sector in active_sectors:
            color = (255, 140, 0)
        else:
            color = (50, 50, 50)

        draw_sector(screen, center, start_angle, end_angle, SECTOR_INNER_RADIUS, SECTOR_OUTER_RADIUS, color)

# ------------------
# BLE CALLBACK
# ------------------

def handle_ble_data(sender, data):

    global latest_heading
    global latest_quaternion
    global last_printed_heading

    try:

        msg = data.decode().strip()

        values = [float(v) for v in msg.split(",")]

        if len(values) != 4:
            return

        w, x, y, z = values

        latest_quaternion = [w, x, y, z]

        # print messages for debugging the received IMU data
        # print(f"RAW: {msg}")
        # print(f"Q = {w:.3f}, {x:.3f}, {y:.3f}, {z:.3f}")

        # changed
        yaw_deg = -quaternion_to_yaw_deg(
            w, x, y, z
        )

        if (
            last_printed_heading is None or
            abs(yaw_deg - last_printed_heading) > 5
        ):
            print(f"Heading: {yaw_deg:.1f}")
            last_printed_heading = yaw_deg

        with heading_lock:
            latest_heading = yaw_deg

    except Exception as e:
        print("BAD IMU MESSAGE:", e)

def send_ble_message(message):

    global ble_loop_ref

    if ble_loop_ref is None:
        return

    asyncio.run_coroutine_threadsafe(
        ble_send(message),
        ble_loop_ref
    )

async def ble_send(message):

    global ble_client

    if ble_client is None:
        return

    try:

        await ble_client.write_gatt_char(
            BLE_TX_UUID,
            message.encode()
        )

    except Exception as e:
        print("BLE SEND FAILED:", e)

# ------------------
# BLE LOOP
# ------------------

async def ble_loop():

    global BLE_ADDRESS

    print("Scanning for Argon...")

    devices = await BleakScanner.discover(timeout=10.0)

    for d in devices:

        print(f"{d.name} | {d.address}")

        if d.name and "Argon" in d.name:
            BLE_ADDRESS = d.address
            break

    if BLE_ADDRESS is None:
        print("Argon not found.")
        return

    print(f"Connecting to {BLE_ADDRESS}")

    async with BleakClient(BLE_ADDRESS) as client:

        global ble_client

        ble_client = client

        print("Connected to BLE device")

        # print("\nSERVICES AND CHARACTERISTICS:")

        # # the below for loop is just for debugging to find the correct characteristic UUIDs, it can be removed once the correct ones are identified and hardcoded above
        # for service in client.services:

        #     print(f"\nSERVICE: {service.uuid}")

        #     for char in service.characteristics:

        #         print(f"  CHARACTERISTIC: {char.uuid}")
        #         print(f"  PROPERTIES: {char.properties}")

        await client.start_notify(
            BLE_RX_UUID,
            handle_ble_data
        )

        while client.is_connected:
            await asyncio.sleep(0.1)
        
        print("BLE disconnected")

# ------------------
# BLE THREAD
# ------------------

def start_ble():

    try:
        global ble_loop_ref

        ble_loop_ref = asyncio.new_event_loop()

        asyncio.set_event_loop(ble_loop_ref)

        ble_loop_ref.run_until_complete(
            ble_loop()
        )

    except Exception as e:
        print("BLE THREAD CRASHED:", e)

ble_thread = threading.Thread(
    target=start_ble,
    daemon=True
)

ble_thread.start()


# ------------------
# MAIN LOOP
# ------------------

running = True

while running:

    # ------------------
    # EVENTS
    # ------------------

    for event in pygame.event.get():

        # quit
        if event.type == pygame.QUIT:
            running = False

        # ------------------
        # MOUSE DOWN
        # ------------------

        if event.type == pygame.MOUSEBUTTONDOWN:

            mx, my = event.pos

            # ------------------
            # LEFT CLICK
            # ------------------

            if event.button == 1:

                clicked_existing = False

                # see if clicking existing threat
                for i, threat in enumerate(THREATS):

                    tx = threat["global_x"]
                    ty = threat["global_y"]

                    dist = math.hypot(tx - mx, ty - my)

                    if dist < 15:

                        drag_index = i
                        clicked_existing = True
                        break

                # otherwise create new threat
                if not clicked_existing:

                    new_threat = {
                        "id": NEXT_THREAT_ID,
                        "global_x": mx,
                        "global_y": my
                    }

                    THREATS.append(new_threat)

                    send_single_threat(new_threat)

                    NEXT_THREAT_ID += 1

            # ------------------
            # RIGHT CLICK
            # ------------------

            if event.button == 3:

                clicked_index = None

                # check if clicking existing threat
                for i, threat in enumerate(THREATS):

                    tx = threat["global_x"]
                    ty = threat["global_y"]

                    dist = math.hypot(tx - mx, ty - my)

                    if dist < 15:
                        clicked_index = i
                        break

                # ------------------
                # REMOVE SINGLE THREAT
                # ------------------

                if clicked_index is not None:

                    threat = THREATS[clicked_index]

                    threat_id = threat["id"]

                    tx = threat["global_x"]
                    ty = threat["global_y"]

                    global_x = tx - CENTER[0]
                    global_y = CENTER[1] - ty

                    removal_msg = f"{threat_id},{global_x},{global_y},-1"

                    print("TX:", removal_msg)
                    send_ble_message(removal_msg + "\n")

                    THREATS.pop(clicked_index)

                # ------------------
                # REMOVE ALL THREATS
                # ------------------

                else:

                    for threat in THREATS:

                        threat_id = threat["id"]

                        tx = threat["global_x"]
                        ty = threat["global_y"]

                        global_x = tx - CENTER[0]
                        global_y = CENTER[1] - ty

                        removal_msg = f"{threat_id},{global_x},{global_y},-1"

                        print("TX:", removal_msg)
                        send_ble_message(removal_msg + "\n")
                        # uncomment for hardware
                        # ser.write((removal_msg + "\n").encode())

                    THREATS.clear()
        # ------------------
        # MOUSE UP
        # ------------------

        if event.type == pygame.MOUSEBUTTONUP:

            if event.button == 1:
                drag_index = None

        # ------------------
        # MOUSE MOTION
        # ------------------

        if event.type == pygame.MOUSEMOTION:

            if drag_index is not None:

                threat = THREATS[drag_index]

                threat["global_x"] = event.pos[0]
                threat["global_y"] = event.pos[1]

                send_move_threat(threat)

    # ------------------
    # HEADING INPUT
    # ------------------

    # use BLE heading instead of keyboard:
    with heading_lock:
        user_heading_deg = latest_heading


    # --------- keyboard input
    # keys = pygame.key.get_pressed()

    # if keys[pygame.K_a]:
    #     user_heading_deg += 2

    # if keys[pygame.K_d]:
    #     user_heading_deg -= 2
    # --------- keyboard input

    # ------------------
    # DRAW
    # ------------------

    screen.fill((20, 20, 20))

    # ------------------
    # SECTOR HIGHLIGHTS
    # ------------------
    active_sectors = get_active_sectors(THREATS, user_heading_deg)

    draw_sector_map(screen, CENTER, user_heading_deg, active_sectors)

    # ------------------
    # USER
    # ------------------

    pygame.draw.circle(
        screen,
        (255, 255, 255),
        CENTER,
        20
    )

    # ------------------
    # HEADING ARROW
    # ------------------

    hx = CENTER[0] + 60 * math.sin(
        math.radians(user_heading_deg)
    )

    hy = CENTER[1] - 60 * math.cos(
        math.radians(user_heading_deg)
    )

    pygame.draw.line(
        screen,
        (0, 255, 0),
        CENTER,
        (hx, hy),
        4
    )

    # ------------------
    # THREATS
    # ------------------

    for threat in THREATS:

        tx = threat["global_x"]
        ty = threat["global_y"]

        pygame.draw.circle(
            screen,
            (255, 0, 0),
            (tx, ty),
            10
        )

        # optional: draw threat ID
        font = pygame.font.SysFont(None, 24)

        text = font.render(
            str(threat["id"]),
            True,
            (255, 255, 255)
        )

        screen.blit(text, (tx + 12, ty - 12))

    pygame.display.flip()

    clock.tick(30)  # 30 FPS

pygame.quit()
