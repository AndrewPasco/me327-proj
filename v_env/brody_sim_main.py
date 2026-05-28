# Haptic belt threat simulation — main demo script
#
# Logic:  Ashlynn's simulation (spiral threats, wave schedule, shutdown cleanup)
# UI:     Brody's visualization (single forward cone, lock-on arc, decay mechanic)
#
# Controls:
#   SPACE          — start / restart
#   ← → arrow keys — rotate heading when BLE not connected
#
# BLE connects automatically to "Argon" device.
# Threat message format: spawn/move "id,x,y,0\n"  |  remove "id,x,y,-1\n"
#
# Runs on Python 3.11+ with: pygame, bleak

import pygame
import math
import asyncio
from bleak import BleakScanner, BleakClient
import threading
import random

# ─── CONFIG ──────────────────────────────────────────────────────────────────

WIDTH  = 800
HEIGHT = 800
FPS    = 30
CENTER = (WIDTH // 2, HEIGHT // 2)

METERS_TO_PX     = 300.0 / 500.0   # 500 m = 300 px (outer cone edge)
TERMINAL_M       = 50
TERMINAL_PX      = int(TERMINAL_M * METERS_TO_PX)   # 30 px

LOCK_ON_DURATION = 3.0              # seconds user must face sector to neutralize

NUM_MOTORS   = 8
SECTOR_SIZE  = 360.0 / NUM_MOTORS   # 45 °

SECTOR_INNER_RADIUS = 40
SECTOR_OUTER_RADIUS = 300

RANGE_RINGS_M = [100, 200, 300, 400, 500]

SPIRAL_OMEGA        = 0.2    # rad/s — angular drift rate for spiral threats
SPIRAL_RADIAL_SPEED = 10     # px/s  — inward speed for spiral threats

WAVE_CLEAR_DELAY = 3.0       # seconds between a wave being cleared and the next spawning

# Wave schedule (Ashlynn's).
# spawn_time: seconds after SPACE pressed. Wave 1 at T=3 gives a natural countdown.
# angle_deg: compass bearing FROM WHICH the threat approaches (0=N, 90=E, …).
WAVE_SCHEDULE = [
    {
        "spawn_time": 3.0,
        "label": "WAVE 1",
        "threats": [
            {"angle_deg":   0, "speed_mps": 10, "distance_m": 400},
            {"angle_deg": 175, "speed_mps": 10, "distance_m": 400},
        ],
    },
    {
        "spawn_time": 18.0,
        "label": "WAVE 2",
        "threats": [
            {"angle_deg":  45, "speed_mps": 12, "distance_m": 500},
            {"angle_deg": 225, "speed_mps": 12, "distance_m": 500},
        ],
    },
    {
        "spawn_time": 33.0,
        "label": "WAVE 3",
        "threats": [
            {"angle_deg":  30, "speed_mps": 14, "distance_m": 500},
            {"angle_deg": 160, "speed_mps": 14, "distance_m": 500},
            {"angle_deg": 290, "speed_mps": 14, "distance_m": 500},
        ],
    },
    {
        "spawn_time": 48.0,
        "label": "WAVE 4",
        "threats": [
            {"angle_deg":  10, "speed_mps": 16, "distance_m": 500},
            {"angle_deg": 130, "speed_mps": 16, "distance_m": 500},
            {"angle_deg": 250, "speed_mps": 16, "distance_m": 500},
        ],
    },
]

TOTAL_THREATS = sum(len(w["threats"]) for w in WAVE_SCHEDULE)

# ─── BLE GLOBALS ─────────────────────────────────────────────────────────────

BLE_ADDRESS   = None
ble_client    = None
ble_loop_ref  = None
ble_connected = False
ble_status    = "scanning"   # "scanning" | "connected" | "not found" | "disconnected"

BLE_RX_UUID = "62c3cf89-247b-4c0f-a70d-651080844608"
BLE_TX_UUID = "62c3cf89-247b-4c0f-a70d-651080844609"

latest_heading       = 0.0
heading_lock         = threading.Lock()
last_printed_heading = None

# ─── GAME STATE ──────────────────────────────────────────────────────────────

STATE_INTRO   = "intro"
STATE_PLAYING = "playing"
STATE_END     = "end"

state             = STATE_INTRO
game_time         = 0.0
threats           = []
animations        = []
screen_flash      = None
next_threat_id    = 0
waves_spawned     = 0
current_wave_num  = 0
misses            = 0
neutralized_count = 0
wave_notification = None
next_wave_timer   = None     # counts down after a wave clears before spawning the next
user_heading_deg  = 0.0

# ─── PYGAME INIT ─────────────────────────────────────────────────────────────

pygame.init()
screen_surf = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Threat Simulation")
clock = pygame.time.Clock()

font_xl    = pygame.font.SysFont(None, 80)
font_large = pygame.font.SysFont(None, 56)
font_med   = pygame.font.SysFont(None, 36)
font_small = pygame.font.SysFont(None, 24)

# ─── GEOMETRY ────────────────────────────────────────────────────────────────

def bearing_to_screen(bearing_deg, distance_px):
    rad = math.radians(bearing_deg)
    return (CENTER[0] + distance_px * math.sin(rad),
            CENTER[1] - distance_px * math.cos(rad))

def get_threat_relative_angle(threat, heading_deg):
    dx = threat["x"] - CENTER[0]
    dy = CENTER[1]   - threat["y"]
    return (math.degrees(math.atan2(dx, dy)) - heading_deg) % 360

def get_threat_sector(threat, heading_deg):
    angle = get_threat_relative_angle(threat, heading_deg)
    return int(((angle + SECTOR_SIZE / 2) % 360) // SECTOR_SIZE)

def screen_to_global(x, y):
    return x - CENTER[0], CENTER[1] - y

# ─── BLE ─────────────────────────────────────────────────────────────────────

def quaternion_to_yaw_deg(w, x, y, z):
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.degrees(math.atan2(siny_cosp, cosy_cosp))

def handle_ble_data(sender, data):
    global latest_heading, last_printed_heading
    try:
        values = [float(v) for v in data.decode().strip().split(",")]
        if len(values) != 4:
            return
        w, x, y, z = values
        yaw = -quaternion_to_yaw_deg(w, x, y, z)
        if last_printed_heading is None or abs(yaw - last_printed_heading) > 5:
            print(f"Heading: {yaw:.1f}°")
            last_printed_heading = yaw
        with heading_lock:
            latest_heading = yaw
    except Exception as e:
        print("BAD IMU:", e)

def send_ble_message(msg):
    if ble_loop_ref is None:
        return
    asyncio.run_coroutine_threadsafe(_ble_write(msg), ble_loop_ref)

async def _ble_write(msg):
    if ble_client is None:
        return
    try:
        await ble_client.write_gatt_char(BLE_TX_UUID, msg.encode())
    except Exception as e:
        print("BLE SEND FAILED:", e)

async def ble_loop():
    global BLE_ADDRESS, ble_client, ble_connected, ble_status
    print("Scanning for Argon...")
    devices = await BleakScanner.discover(timeout=10.0)
    for d in devices:
        print(f"  {d.name} | {d.address}")
        if d.name and "Argon" in d.name:
            BLE_ADDRESS = d.address
            break
    if BLE_ADDRESS is None:
        print("Argon not found.")
        ble_status = "not found"
        return
    print(f"Connecting to {BLE_ADDRESS}…")
    async with BleakClient(BLE_ADDRESS) as client:
        ble_client    = client
        ble_connected = True
        ble_status    = "connected"
        print("BLE connected.")
        await client.start_notify(BLE_RX_UUID, handle_ble_data)
        while client.is_connected:
            await asyncio.sleep(0.1)
        ble_connected = False
        ble_status    = "disconnected"
        print("BLE disconnected.")

def _start_ble():
    global ble_loop_ref
    try:
        ble_loop_ref = asyncio.new_event_loop()
        asyncio.set_event_loop(ble_loop_ref)
        ble_loop_ref.run_until_complete(ble_loop())
    except Exception as e:
        print("BLE THREAD CRASHED:", e)

threading.Thread(target=_start_ble, daemon=True).start()

# ─── BLE THREAT MESSAGES ─────────────────────────────────────────────────────

def ble_spawn(threat):
    gx, gy = screen_to_global(threat["x"], threat["y"])
    msg = f"{threat['id']},{gx:.0f},{gy:.0f},0"
    print("TX (spawn):", msg)
    send_ble_message(msg + "\n")

def ble_move(threat):
    gx, gy = screen_to_global(threat["x"], threat["y"])
    send_ble_message(f"{threat['id']},{gx:.0f},{gy:.0f},0\n")

def ble_remove(threat):
    gx, gy = screen_to_global(threat["x"], threat["y"])
    msg = f"{threat['id']},{gx:.0f},{gy:.0f},-1"
    print("TX (remove):", msg)
    send_ble_message(msg + "\n")

# ─── GAME LOGIC (Ashlynn's) ──────────────────────────────────────────────────

def spawn_threat(template, wave_idx):
    global next_threat_id
    dist_px  = template["distance_m"] * METERS_TO_PX
    speed_px = template["speed_mps"]  * METERS_TO_PX
    x, y     = bearing_to_screen(template["angle_deg"], dist_px)
    dx, dy   = CENTER[0] - x, CENTER[1] - y
    norm     = math.hypot(dx, dy)
    theta    = math.atan2(CENTER[1] - y, x - CENTER[0])
    is_spiral = random.random() < 0.2   # 20% chance of spiral trajectory
    threat = {
        "id":           next_threat_id,
        "x":            x,
        "y":            y,
        "vx":           speed_px * dx / norm,
        "vy":           speed_px * dy / norm,
        "theta":        theta,
        "radius":       math.hypot(x - CENTER[0], y - CENTER[1]),
        "radial_speed": SPIRAL_RADIAL_SPEED,
        "omega":        SPIRAL_OMEGA,
        "mode":         "spiral" if is_spiral else "straight",
        "lock_on":      0.0,
        "ble_timer":    0.0,
        "wave":         wave_idx,
    }
    next_threat_id += 1
    threats.append(threat)
    ble_spawn(threat)

def neutralize_threat(threat):
    global neutralized_count, screen_flash
    neutralized_count += 1
    threats.remove(threat)
    animations.append({
        "type": "neutralize",
        "x": threat["x"], "y": threat["y"],
        "timer": 0.8, "duration": 0.8,
    })
    screen_flash = {"color": (0, 200, 0), "timer": 0.3, "duration": 0.3}
    ble_remove(threat)
    print(f"Neutralized threat {threat['id']}")

def shutdown_all_threats():
    for t in list(threats):
        ble_remove(t)
    threats.clear()

def terminal_hit(threat):
    global misses, screen_flash
    misses += 1
    threats.remove(threat)
    animations.append({
        "type": "terminal",
        "x": threat["x"], "y": threat["y"],
        "timer": 0.9, "duration": 0.9,
    })
    screen_flash = {"color": (220, 0, 0), "timer": 0.5, "duration": 0.5}
    ble_remove(threat)
    print(f"TERMINAL HIT — threat {threat['id']}")

def reset_game():
    global state, game_time, threats, animations, screen_flash
    global next_threat_id, waves_spawned, current_wave_num
    global misses, neutralized_count, wave_notification, next_wave_timer
    state             = STATE_INTRO
    game_time         = 0.0
    screen_flash      = None
    next_threat_id    = 0
    waves_spawned     = 0
    current_wave_num  = 0
    misses            = 0
    neutralized_count = 0
    wave_notification = None
    next_wave_timer   = None
    threats.clear()
    animations.clear()

# ─── DRAWING (Brody's UI) ────────────────────────────────────────────────────

def draw_range_rings(surf):
    for m in RANGE_RINGS_M:
        r = int(m * METERS_TO_PX)
        pygame.draw.circle(surf, (55, 55, 55), CENTER, r, 1)
        label = font_small.render(f"{m}m", True, (75, 75, 75))
        surf.blit(label, (CENTER[0] + r + 3, CENTER[1] - 10))

def draw_dashed_circle(surf, color, center, radius, dashes=32, width=2):
    for i in range(dashes):
        a0 = 2 * math.pi *  i        / dashes
        a1 = 2 * math.pi * (i + 0.5) / dashes
        x0 = int(center[0] + radius * math.cos(a0))
        y0 = int(center[1] + radius * math.sin(a0))
        x1 = int(center[0] + radius * math.cos(a1))
        y1 = int(center[1] + radius * math.sin(a1))
        pygame.draw.line(surf, color, (x0, y0), (x1, y1), width)

def draw_sector_shape(surf, center, start_deg, end_deg, inner_r, outer_r,
                      color, border=(120, 120, 120), bwidth=2, res=20):
    pts = []
    for i in range(res + 1):
        a = math.radians(start_deg + (end_deg - start_deg) * i / res)
        pts.append((center[0] + outer_r * math.sin(a),
                    center[1] - outer_r * math.cos(a)))
    for i in range(res, -1, -1):
        a = math.radians(start_deg + (end_deg - start_deg) * i / res)
        pts.append((center[0] + inner_r * math.sin(a),
                    center[1] - inner_r * math.cos(a)))
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, border, pts, bwidth)

def draw_forward_cone(surf, heading_deg, threats):
    """Single 45° forward wedge — shifts orange → green as lock-on builds."""
    a0      = heading_deg - SECTOR_SIZE / 2
    a1      = heading_deg + SECTOR_SIZE / 2
    in_cone = [t for t in threats if get_threat_sector(t, heading_deg) == 0]
    if in_cone:
        best     = max(t["lock_on"] for t in in_cone)
        progress = best / LOCK_ON_DURATION
        color    = (int(255 * (1.0 - progress)), int(140 + 70 * progress), 0)
        border   = (80, 160, 80) if progress > 0.1 else (160, 100, 0)
    else:
        color  = (55, 55, 85)
        border = (90, 90, 110)
    draw_sector_shape(surf, CENTER, a0, a1,
                      SECTOR_INNER_RADIUS, SECTOR_OUTER_RADIUS, color, border)

def draw_cardinal_labels(surf):
    r = SECTOR_OUTER_RADIUS + 18
    for label_str, bearing in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
        bx, by = bearing_to_screen(bearing, r)
        lbl = font_small.render(label_str, True, (150, 150, 150))
        surf.blit(lbl, (int(bx) - lbl.get_width() // 2,
                        int(by) - lbl.get_height() // 2))

def draw_lock_on_arc(surf, threat):
    """Yellow → green clockwise arc around threat dot showing lock-on progress."""
    progress = threat["lock_on"] / LOCK_ON_DURATION
    if progress <= 0:
        return
    cx, cy = int(threat["x"]), int(threat["y"])
    r      = 16
    n      = max(int(30 * progress), 3)
    sweep  = 2 * math.pi * progress
    pts    = [(cx + r * math.sin(sweep * i / n),
               cy - r * math.cos(sweep * i / n)) for i in range(n + 1)]
    color  = (int(255 * (1.0 - progress)), 255, 0)
    if len(pts) >= 2:
        pygame.draw.lines(surf, color, False, pts, 3)

def draw_threats(surf):
    for t in threats:
        tx, ty = int(t["x"]), int(t["y"])
        # Spiral threats shown in purple to distinguish from straight (red)
        color = (180, 60, 220) if t["mode"] == "spiral" else (220, 30, 30)
        pygame.draw.circle(surf, color, (tx, ty), 10)
        draw_lock_on_arc(surf, t)
        lbl = font_small.render(str(t["id"]), True, (255, 255, 255))
        surf.blit(lbl, (tx + 13, ty - 10))

def draw_animations(surf):
    for anim in animations:
        p  = 1.0 - anim["timer"] / anim["duration"]
        cx, cy = int(anim["x"]), int(anim["y"])
        if anim["type"] == "neutralize":
            pygame.draw.circle(surf, (0, 255, 90),    (cx, cy), max(1, int(10 + p * 65)), 3)
            pygame.draw.circle(surf, (180, 255, 180), (cx, cy), max(1, int(10 + p * 32)), 2)
        elif anim["type"] == "terminal":
            pygame.draw.circle(surf, (255, 50,  0),   (cx, cy), max(1, int(p * 55)), 3)
            pygame.draw.circle(surf, (255, 200, 0),   (cx, cy), max(1, int(p * 28)), 2)

def draw_user(surf):
    pygame.draw.circle(surf, (255, 255, 255), CENTER, 20)

def draw_heading_arrow(surf, heading_deg):
    hx, hy = bearing_to_screen(heading_deg, 60)
    pygame.draw.line(surf, (0, 255, 0), CENTER, (int(hx), int(hy)), 4)

def draw_screen_flash(surf):
    if screen_flash is None:
        return
    alpha = max(0, min(180, int(180 * screen_flash["timer"] / screen_flash["duration"])))
    flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    r, g, b = screen_flash["color"]
    flash.fill((r, g, b, alpha))
    surf.blit(flash, (0, 0))

def draw_hud(surf):
    ble_color_map = {
        "scanning":     (255, 200,  0),
        "connected":    (  0, 220,  0),
        "not found":    (200,  80, 80),
        "disconnected": (200, 100,  0),
    }
    ble_col  = ble_color_map.get(ble_status, (200, 200, 200))
    surf.blit(font_small.render(f"BLE: {ble_status}", True, ble_col),
              (WIDTH - font_small.size(f"BLE: {ble_status}")[0] - 10, 10))

    surf.blit(font_small.render(f"Wave {current_wave_num} / {len(WAVE_SCHEDULE)}", True, (200, 200, 200)), (10, 10))
    surf.blit(font_small.render(f"Neutralized: {neutralized_count}   Misses: {misses}", True, (200, 200, 200)), (10, 32))
    surf.blit(font_small.render(f"Heading: {user_heading_deg % 360:.0f}°", True, (140, 210, 140)), (10, 54))

    if not ble_connected:
        hint = font_small.render("← → arrow keys to rotate heading (no BLE)", True, (110, 110, 110))
        surf.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 28))

def draw_wave_notification(surf):
    if wave_notification is None:
        return
    p     = wave_notification["timer"] / 2.0
    alpha = max(0, min(255, int(255 * min(p * 5, 1.0))))
    text  = font_large.render(wave_notification["label"] + " INCOMING", True, (255, 210, 0))
    text.set_alpha(alpha)
    surf.blit(text, (WIDTH  // 2 - text.get_width()  // 2,
                     HEIGHT // 2 - SECTOR_OUTER_RADIUS - 60))

def draw_countdown(surf, seconds_remaining):
    text = font_med.render(f"Simulation begins in {math.ceil(seconds_remaining)}...", True, (180, 180, 180))
    surf.blit(text, (WIDTH  // 2 - text.get_width()  // 2,
                     HEIGHT // 2 + SECTOR_OUTER_RADIUS + 20))

def draw_between_wave_countdown(surf, seconds_remaining):
    text = font_med.render(f"Next wave in {math.ceil(seconds_remaining)}...", True, (180, 180, 180))
    surf.blit(text, (WIDTH  // 2 - text.get_width()  // 2,
                     HEIGHT // 2 + SECTOR_OUTER_RADIUS + 20))

def draw_intro(surf):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 185))
    surf.blit(overlay, (0, 0))

    title = font_xl.render("THREAT SIMULATION", True, (255, 255, 255))
    surf.blit(title, (WIDTH // 2 - title.get_width() // 2, 120))

    lines = [
        "Threats approach from multiple directions across 4 waves.",
        "Face a threat sector for 3 seconds to neutralize it.",
        "Don't let threats reach the danger zone (inner red ring).",
        "",
        "Each new wave spawns on a timer — threats can overlap.",
        "Prioritize the closest threats first.",
        #"",
        #"← → arrow keys rotate heading if no BLE device connected.",
    ]
    y = 240
    for line in lines:
        t = font_med.render(line, True, (195, 195, 195))
        surf.blit(t, (WIDTH // 2 - t.get_width() // 2, y))
        y += 38

    if (pygame.time.get_ticks() // 500) % 2:
        prompt = font_large.render("PRESS SPACE TO BEGIN", True, (255, 220, 0))
        surf.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, y + 20))

def draw_end(surf):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    surf.blit(overlay, (0, 0))

    if misses == 0:
        result_color, result_text = (0, 255, 110), "MISSION COMPLETE"
    else:
        result_color, result_text = (255, 60, 60), "MISSION FAILED"

    title = font_xl.render(result_text, True, result_color)
    surf.blit(title, (WIDTH // 2 - title.get_width() // 2, 190))

    y = 320
    for s in [f"Threats neutralized:  {neutralized_count} / {TOTAL_THREATS}",
              f"Threats missed:       {misses} / {TOTAL_THREATS}"]:
        t = font_med.render(s, True, (220, 220, 220))
        surf.blit(t, (WIDTH // 2 - t.get_width() // 2, y))
        y += 52

    if (pygame.time.get_ticks() // 600) % 2:
        prompt = font_med.render("PRESS SPACE TO RESTART", True, (190, 190, 190))
        surf.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, y + 30))

# ─── MAIN LOOP ───────────────────────────────────────────────────────────────

running = True

while running:
    dt = clock.tick(FPS) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            if state == STATE_INTRO:
                state     = STATE_PLAYING
                game_time = 0.0
            elif state == STATE_END:
                reset_game()

    if state == STATE_PLAYING:
        game_time += dt

        # Heading: BLE takes priority; fall back to arrow keys
        with heading_lock:
            ble_hdg = latest_heading
        if ble_connected:
            user_heading_deg = ble_hdg
        else:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                user_heading_deg -= 90 * dt
            if keys[pygame.K_RIGHT]:
                user_heading_deg += 90 * dt
            user_heading_deg %= 360

        # Wave 1: spawn after the initial 3-second countdown
        if waves_spawned == 0 and game_time >= WAVE_SCHEDULE[0]["spawn_time"]:
            wave = WAVE_SCHEDULE[0]
            for tmpl in wave["threats"]:
                spawn_threat(tmpl, 0)
            current_wave_num  = 1
            wave_notification = {"label": wave["label"], "timer": 2.0}
            waves_spawned     = 1

        # Waves 2-4: only spawn once all previous threats are cleared
        elif 0 < waves_spawned < len(WAVE_SCHEDULE) and not threats:
            if next_wave_timer is None:
                next_wave_timer = WAVE_CLEAR_DELAY   # start countdown
            next_wave_timer -= dt
            if next_wave_timer <= 0:
                next_wave_timer = None
                wave = WAVE_SCHEDULE[waves_spawned]
                for tmpl in wave["threats"]:
                    spawn_threat(tmpl, waves_spawned)
                current_wave_num  = waves_spawned + 1
                wave_notification = {"label": wave["label"], "timer": 2.0}
                waves_spawned    += 1

        if wave_notification:
            wave_notification["timer"] -= dt
            if wave_notification["timer"] <= 0:
                wave_notification = None

        for t in list(threats):
            # Ashlynn's movement: straight or spiral
            if t["mode"] == "straight":
                t["x"] += t["vx"] * dt
                t["y"] += t["vy"] * dt
            else:
                t["radius"] -= t["radial_speed"] * dt
                t["theta"]  += t["omega"] * dt
                t["x"] = CENTER[0] + t["radius"] * math.sin(t["theta"])
                t["y"] = CENTER[1] - t["radius"] * math.cos(t["theta"])

            t["ble_timer"] -= dt
            if t["ble_timer"] <= 0:
                ble_move(t)
                t["ble_timer"] = 0.1

            # Lock-on: accumulate when facing, decay at 2× speed when not
            if get_threat_sector(t, user_heading_deg) == 0:
                t["lock_on"] = min(t["lock_on"] + dt, LOCK_ON_DURATION)
            else:
                t["lock_on"] = max(0.0, t["lock_on"] - dt * 2)

            if t["lock_on"] >= LOCK_ON_DURATION:
                neutralize_threat(t)
                continue

            if math.hypot(t["x"] - CENTER[0], t["y"] - CENTER[1]) <= TERMINAL_PX:
                terminal_hit(t)
                continue

        for a in list(animations):
            a["timer"] -= dt
            if a["timer"] <= 0:
                animations.remove(a)

        if screen_flash:
            screen_flash["timer"] -= dt
            if screen_flash["timer"] <= 0:
                screen_flash = None

        if waves_spawned >= len(WAVE_SCHEDULE) and not threats:
            shutdown_all_threats()
            state = STATE_END

    # ── draw ──────────────────────────────────────────────────────────────
    screen_surf.fill((20, 20, 20))

    draw_range_rings(screen_surf)
    draw_dashed_circle(screen_surf, (180, 40, 40), CENTER, TERMINAL_PX, dashes=24, width=2)
    draw_cardinal_labels(screen_surf)
    draw_forward_cone(screen_surf, user_heading_deg, threats)

    draw_animations(screen_surf)
    draw_user(screen_surf)
    draw_heading_arrow(screen_surf, user_heading_deg)
    draw_threats(screen_surf)

    draw_screen_flash(screen_surf)
    draw_hud(screen_surf)
    draw_wave_notification(screen_surf)

    if state == STATE_PLAYING:
        if waves_spawned == 0:
            remaining = WAVE_SCHEDULE[0]["spawn_time"] - game_time
            if remaining > 0:
                draw_countdown(screen_surf, remaining)
        elif next_wave_timer is not None:
            draw_between_wave_countdown(screen_surf, next_wave_timer)

    if state == STATE_INTRO:
        draw_intro(screen_surf)
    elif state == STATE_END:
        draw_end(screen_surf)

    pygame.display.flip()

pygame.quit()
