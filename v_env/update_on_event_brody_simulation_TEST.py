# TEST VERSION — no BLE, no hardware required
#
# Move your mouse around the center circle to rotate your heading.
# Everything else is identical to update_on_event_brody_simulation.py.
#
# Controls:
#   Mouse  — aim heading (direction from center to cursor)
#   SPACE  — start / restart

import pygame
import math

# ─── CONFIG ──────────────────────────────────────────────────────────────────

WIDTH  = 800
HEIGHT = 800
FPS    = 30
CENTER = (WIDTH // 2, HEIGHT // 2)

METERS_TO_PX     = 300.0 / 500.0
TERMINAL_M       = 50
TERMINAL_PX      = int(TERMINAL_M * METERS_TO_PX)   # 30 px

LOCK_ON_DURATION = 3.0

NUM_MOTORS   = 8
SECTOR_SIZE  = 360.0 / NUM_MOTORS   # 45 °

SECTOR_INNER_RADIUS = 40
SECTOR_OUTER_RADIUS = 300

RANGE_RINGS_M = [100, 200, 300, 400, 500]

WAVE_SCHEDULE = [
    {
        "spawn_time": 3.0,
        "label": "WAVE 1",
        "threats": [
            {"angle_deg":   0, "speed_mps": 16, "distance_m": 400},
            {"angle_deg": 175, "speed_mps": 16, "distance_m": 400},
        ],
    },
    {
        "spawn_time": 12.0,
        "label": "WAVE 2",
        "threats": [
            {"angle_deg":  45, "speed_mps": 19, "distance_m": 500},
            {"angle_deg": 180, "speed_mps": 19, "distance_m": 500},
            {"angle_deg": 315, "speed_mps": 19, "distance_m": 500},
        ],
    },
    {
        "spawn_time": 21.0,
        "label": "WAVE 3",
        "threats": [
            {"angle_deg":  30, "speed_mps": 22, "distance_m": 500},
            {"angle_deg": 120, "speed_mps": 22, "distance_m": 500},
            {"angle_deg": 240, "speed_mps": 22, "distance_m": 500},
            {"angle_deg": 330, "speed_mps": 22, "distance_m": 500},
        ],
    },
    {
        "spawn_time": 30.0,
        "label": "WAVE 4",
        "threats": [
            {"angle_deg":  10, "speed_mps": 25, "distance_m": 500},
            {"angle_deg":  82, "speed_mps": 25, "distance_m": 500},
            {"angle_deg": 154, "speed_mps": 25, "distance_m": 500},
            {"angle_deg": 226, "speed_mps": 25, "distance_m": 500},
            {"angle_deg": 298, "speed_mps": 25, "distance_m": 500},
        ],
    },
]

TOTAL_THREATS = sum(len(w["threats"]) for w in WAVE_SCHEDULE)

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
user_heading_deg  = 0.0

# ─── PYGAME INIT ─────────────────────────────────────────────────────────────

pygame.init()
screen_surf = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Threat Simulation — TEST (mouse = heading)")
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

def heading_from_mouse(mx, my):
    """Compass bearing (clockwise from N) from center to mouse cursor."""
    dx =  mx - CENTER[0]
    dy = CENTER[1] - my    # flip y so up = positive
    return math.degrees(math.atan2(dx, dy)) % 360

def get_threat_relative_angle(threat, heading_deg):
    dx = threat["x"] - CENTER[0]
    dy = CENTER[1]   - threat["y"]
    world_angle = math.degrees(math.atan2(dx, dy))
    return (world_angle - heading_deg) % 360

def get_threat_sector(threat, heading_deg):
    angle = get_threat_relative_angle(threat, heading_deg)
    return int(((angle + SECTOR_SIZE / 2) % 360) // SECTOR_SIZE)

def get_active_sectors(threat_list, heading_deg):
    return {get_threat_sector(t, heading_deg) for t in threat_list}

# ─── STUB BLE (prints only, no hardware) ─────────────────────────────────────

def ble_spawn(threat):
    print(f"[BLE stub] spawn  id={threat['id']}")

def ble_move(threat):
    pass   # suppress per-frame noise

def ble_remove(threat):
    print(f"[BLE stub] remove id={threat['id']}")

# ─── GAME LOGIC ──────────────────────────────────────────────────────────────

def spawn_threat(template, wave_idx):
    global next_threat_id
    dist_px  = template["distance_m"] * METERS_TO_PX
    speed_px = template["speed_mps"]  * METERS_TO_PX
    x, y     = bearing_to_screen(template["angle_deg"], dist_px)
    dx, dy   = CENTER[0] - x, CENTER[1] - y
    norm     = math.hypot(dx, dy)
    threat   = {
        "id":        next_threat_id,
        "x":         x,
        "y":         y,
        "vx":        speed_px * dx / norm,
        "vy":        speed_px * dy / norm,
        "lock_on":   0.0,
        "ble_timer": 0.0,
        "wave":      wave_idx,
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

def reset_game():
    global state, game_time, threats, animations, screen_flash
    global next_threat_id, waves_spawned, current_wave_num
    global misses, neutralized_count, wave_notification
    state             = STATE_INTRO
    game_time         = 0.0
    screen_flash      = None
    next_threat_id    = 0
    waves_spawned     = 0
    current_wave_num  = 0
    misses            = 0
    neutralized_count = 0
    wave_notification = None
    threats.clear()
    animations.clear()

# ─── DRAWING ─────────────────────────────────────────────────────────────────

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
        pygame.draw.line(surf, color,
                         (int(center[0] + radius * math.cos(a0)),
                          int(center[1] + radius * math.sin(a0))),
                         (int(center[0] + radius * math.cos(a1)),
                          int(center[1] + radius * math.sin(a1))), width)

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

def draw_sector_wheel(surf, heading_deg, active_sectors, locked_on):
    for s in range(NUM_MOTORS):
        a0 = heading_deg - SECTOR_SIZE / 2 + s * SECTOR_SIZE
        a1 = a0 + SECTOR_SIZE
        if s == 0 and locked_on:
            color = (80, 210, 80)
        elif s in active_sectors:
            color = (255, 140, 0)
        elif s == 0:
            color = (60, 60, 95)
        else:
            color = (50, 50, 50)
        draw_sector_shape(surf, CENTER, a0, a1,
                          SECTOR_INNER_RADIUS, SECTOR_OUTER_RADIUS, color)

def draw_cardinal_labels(surf):
    r = SECTOR_OUTER_RADIUS + 18
    for label_str, bearing in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
        bx, by = bearing_to_screen(bearing, r)
        lbl = font_small.render(label_str, True, (150, 150, 150))
        surf.blit(lbl, (int(bx) - lbl.get_width() // 2,
                        int(by) - lbl.get_height() // 2))

def draw_lock_on_arc(surf, threat):
    progress = threat["lock_on"] / LOCK_ON_DURATION
    if progress <= 0:
        return
    cx, cy = int(threat["x"]), int(threat["y"])
    r, n   = 16, max(int(30 * progress), 3)
    sweep  = 2 * math.pi * progress
    pts    = [(cx + r * math.sin(sweep * i / n),
               cy - r * math.cos(sweep * i / n)) for i in range(n + 1)]
    color  = (int(255 * (1.0 - progress)), 255, 0)
    if len(pts) >= 2:
        pygame.draw.lines(surf, color, False, pts, 3)

def draw_threats(surf):
    for t in threats:
        tx, ty = int(t["x"]), int(t["y"])
        pygame.draw.circle(surf, (220, 30, 30), (tx, ty), 10)
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

def draw_screen_flash(surf):
    if screen_flash is None:
        return
    alpha = max(0, min(180, int(180 * screen_flash["timer"] / screen_flash["duration"])))
    flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    r, g, b = screen_flash["color"]
    flash.fill((r, g, b, alpha))
    surf.blit(flash, (0, 0))

def draw_hud(surf):
    wave_str  = f"Wave {current_wave_num} / {len(WAVE_SCHEDULE)}"
    score_str = f"Neutralized: {neutralized_count}   Misses: {misses}"
    hdg_str   = f"Heading: {user_heading_deg % 360:.0f}°"
    surf.blit(font_small.render(wave_str,  True, (200, 200, 200)), (10, 10))
    surf.blit(font_small.render(score_str, True, (200, 200, 200)), (10, 32))
    surf.blit(font_small.render(hdg_str,   True, (140, 210, 140)), (10, 54))

    tag = font_small.render("TEST MODE — mouse controls heading", True, (100, 180, 255))
    surf.blit(tag, (WIDTH - tag.get_width() - 10, 10))

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
    n    = math.ceil(seconds_remaining)
    text = font_med.render(f"Simulation begins in {n}...", True, (180, 180, 180))
    surf.blit(text, (WIDTH  // 2 - text.get_width()  // 2,
                     HEIGHT // 2 + SECTOR_OUTER_RADIUS + 20))

def draw_intro(surf):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 185))
    surf.blit(overlay, (0, 0))

    title = font_xl.render("THREAT SIMULATION", True, (255, 255, 255))
    surf.blit(title, (WIDTH // 2 - title.get_width() // 2, 120))

    tag = font_med.render("— TEST MODE —", True, (100, 180, 255))
    surf.blit(tag, (WIDTH // 2 - tag.get_width() // 2, 205))

    lines = [
        "Move your mouse around the center to rotate your heading.",
        "",
        "Face a threat sector for 3 seconds to neutralize it.",
        "Don't let threats reach the danger zone (inner red ring).",
        "",
        "Each new wave spawns on a timer — threats can overlap.",
        "Prioritize the closest threats first.",
    ]
    y = 270
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
        result_color, result_text = (255, 60, 60),  "MISSION FAILED"

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

    # Heading from mouse position
    mx, my = pygame.mouse.get_pos()
    if state == STATE_PLAYING:
        user_heading_deg = heading_from_mouse(mx, my)

    if state == STATE_PLAYING:
        game_time += dt

        # Wave spawning
        while waves_spawned < len(WAVE_SCHEDULE):
            wave = WAVE_SCHEDULE[waves_spawned]
            if game_time < wave["spawn_time"]:
                break
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
            t["x"] += t["vx"] * dt
            t["y"] += t["vy"] * dt

            if get_threat_sector(t, user_heading_deg) == 0:
                t["lock_on"] += dt
            else:
                t["lock_on"] = 0.0

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
            state = STATE_END

    # ── draw ──────────────────────────────────────────────────────────────
    screen_surf.fill((20, 20, 20))

    draw_range_rings(screen_surf)
    draw_dashed_circle(screen_surf, (180, 40, 40), CENTER, TERMINAL_PX, dashes=24, width=2)
    draw_cardinal_labels(screen_surf)

    active_sectors = get_active_sectors(threats, user_heading_deg)
    locked_on      = any(
        get_threat_sector(t, user_heading_deg) == 0 and t["lock_on"] > 0
        for t in threats
    )
    draw_sector_wheel(screen_surf, user_heading_deg, active_sectors, locked_on)

    draw_animations(screen_surf)
    pygame.draw.circle(screen_surf, (255, 255, 255), CENTER, 20)
    bx, by = bearing_to_screen(user_heading_deg, 60)
    pygame.draw.line(screen_surf, (0, 255, 0), CENTER, (int(bx), int(by)), 4)
    draw_threats(screen_surf)

    draw_screen_flash(screen_surf)
    draw_hud(screen_surf)
    draw_wave_notification(screen_surf)

    if state == STATE_PLAYING and waves_spawned == 0:
        remaining = WAVE_SCHEDULE[0]["spawn_time"] - game_time
        if remaining > 0:
            draw_countdown(screen_surf, remaining)

    if state == STATE_INTRO:
        draw_intro(screen_surf)
    elif state == STATE_END:
        draw_end(screen_surf)

    pygame.display.flip()

pygame.quit()
