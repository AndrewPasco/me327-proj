# ME327 Haptic Belt: Covert Early Warning Communication System

> **ME327: Design and Control of Haptic Systems — Team 14**  
> Joseph Heimerl · Andrew Pasco · Ashlynn Sweet · Brody Todd

A wearable haptic belt that translates aerial threat detections (e.g., UAV positions) into real-time directional tactile cues. Eight coin-style ERM vibration motors spaced around the waist give the operator a passive, silent, always-on awareness of threats in their environment.

---

## How It Works

1. A **host computer** (running a threat-detection or simulation pipeline) detects a threat and encodes its position as `(x, y, z)` coordinates in a local frame.
2. The host sends a BLE packet to the belt controller (Particle Argon).
3. The **BNO085 IMU** continuously provides the operator's orientation as a quaternion.
4. The firmware computes the **relative bearing** from the operator to the threat, selects the nearest motor(s), and drives them at an intensity inversely proportional to threat range.
5. The belt simultaneously streams the current orientation quaternion back to the host for visualization.

As the operator turns, the vibration pattern rotates with them — always pointing toward the threat in the operator's frame.

---

## Repository Structure

```
me327-proj/
├── Analysis/                          # Vibration analysis
│   └── Analysis.m                     # MATLAB 2-DOF housing vibration model
├── CAD/                               # 3D-printed housing and belt buckle STL files
├── belt_controller/                   # Earlier prototype firmware (reference)
├── controllerTest/                    # Firmware + host BLE utilities
│   ├── controllerTest/                # Particle Workbench project
│   │   ├── src/                       # All firmware source
│   │   │   ├── controllerTest.cpp     # Entry point (setup / loop)
│   │   │   ├── HapticBelt.h/.cpp      # Top-level orchestrator
│   │   │   ├── BeltBLE.h/.cpp         # BLE peripheral (Rx threats / Tx orientation)
│   │   │   ├── BeltIMU.h/.cpp         # IMU interface + quaternion math
│   │   │   ├── ThreatTracker.h/.cpp   # Threat state machine (parse + store)
│   │   │   ├── HapticSignature.h      # Temporal vibration patterns per threat
│   │   │   └── MotorDriver.h/.cpp     # PWM abstraction for 8 ERM motors
│   │   ├── lib/                       # Vendored libraries
│   │   │   ├── Adafruit_BNO08x_Sahagun/
│   │   │   ├── Adafruit_BusIO_Sahagun/
│   │   │   └── Adafruit_Unified_Sensor_Sahagun/
│   │   └── project.properties         # Particle project config + dependencies
│   ├── bleakListener.py               # Host: receive orientation from belt (debug)
│   ├── bleakScanAndListen             # Host: scan + connect by device name
│   ├── bleakScanner                   # Host: passive BLE scanner
│   └── serialListener.py              # Host: USB Serial monitor
├── docs/                              # Design notes and project documentation checkpoints
├── media/                             # Visual assets for the project documentation
├── v_env/                             # Host-side GUI & threat simulation scripts
│   ├── brody_sim_main.py              # Main demo simulation (waves + spiral threats)
│   ├── gui_ashlynn_sim.py             # Game-mode simulation (4 escalating waves)
│   ├── gui_update_on_event.py         # Interactive debug / intro GUI (click-to-place)
│   ├── gui_drag_and_drop.py           # Drag-and-drop threat placement
│   ├── gui_single.py                  # Single-threat GUI
│   ├── gui_mult.py                    # Multi-threat GUI
│   ├── gui_varforce.py                # Variable-force multi-threat GUI
│   ├── gui_update_continously.py      # Continuous-update visualization
│   ├── update_on_event_brody_simulation.py      # BLE simulation + mouse test
│   ├── update_on_event_brody_simulation_TEST.py # Test variant of above
│   ├── pyproject.toml                 # Python project configuration
│   └── uv.lock                        # Lockfile for Python dependencies
├── architecture.md                    # Detailed design and architecture document
├── LICENSE                            # MIT License
└── README.md                          # This file
```

---

## Hardware

| Component | Part | Notes |
| :--- | :--- | :--- |
| Microcontroller | Particle Argon (nRF52840) | BLE, I2C, 12 PWM pins |
| IMU | BNO085 (I2C) | Game Rotation Vector report @ ~100 Hz |
| Motor Drivers | DRV8833 ×4 | 2 motors per driver, PWM control |
| Actuators | 8× coin ERM vibration motors | Equally spaced around waist |
| Structure | Elastic belt + 3D-printed clamshell housings | Rigid skin contact |

### Pin Mapping (Particle Argon)

| Resource | Pins |
| :--- | :--- |
| IMU (I2C) | SDA / SCL (default bus) |
| Motor 0 (forward) | D5 |
| Motor 1 | A5 |
| Motor 2 | A4 |
| Motor 3 | A2 |
| Motor 4 | A1 |
| Motor 5 | D6 |
| Motor 6 | D8 |
| Motor 7 | D4 |
| Status LED | D7 (onboard) |

---

## Firmware

### Building & Flashing

The firmware is a [Particle Workbench](https://docs.particle.io/tools/developer-tools/workbench/) project.

1. Open `controllerTest/controllerTest/` in VS Code with the Particle Workbench extension installed.
2. Select your target device (Argon) and Device OS version.
3. Run **Particle: Flash application (local)** or use the Particle CLI:

```bash
particle flash --usb controllerTest
```

### Software Modules

See [`architecture.md`](architecture.md) for the full design document. In brief:

| Module | Class | Purpose |
|:---|:---|:---|
| Orchestrator | `HapticBelt` | Ties all subsystems together; owns the main `loop()` |
| BLE | `BeltBLE` | GATT peripheral; Rx threat packets, Tx orientation quaternion |
| IMU | `BeltIMU` | BNO085 driver; quaternion re-orientation, reset recovery |
| Threat State | `ThreatTracker` | Parses BLE packets; maintains up to 10 active threats |
| Haptic Signatures | `HapticSignature` | Temporal vibration patterns (on/off timing) per threat for tactile differentiation |
| Motors | `MotorDriver` | PWM abstraction for 8 ERMs at 500 Hz |

### BLE Protocol

The belt advertises as **`"Argon Test"`** over BLE with service UUID `62c3cf89-247b-4c0f-a70d-651080844609`.

**Host → Belt (Rx characteristic `...844609`)**

Semicolon-separated threat packets, UTF-8 encoded:
```
"<id>,<x>,<y>,<z>[;<id>,<x>,<y>,<z>;...]"
```
- `id`: integer threat identifier (0–9; each slot has a unique haptic signature)
- `x`, `y`: position in the host's local frame (meters or arbitrary units; `+x` = right, `+y` = forward)
- `z`: depth / altitude — set to `-1` to **remove** a threat

**Belt → Host (Tx characteristic `...844608`)**

Orientation quaternion, sent as a comma-separated string each loop:
```
"<w>,<x>,<y>,<z>"
```

---

## Host-Side Python Tools

### BLE Debug Utilities

Located in `controllerTest/`. Dependencies managed with `uv`.

```bash
# Install dependencies
cd controllerTest
uv add bleak

# Listen for orientation packets from the belt
uv run bleakListener.py

# Scan for the belt and listen
uv run bleakScanAndListen

# USB Serial monitor (no BLE required)
uv run serialListener.py
```

> **Device MAC address** is printed over USB Serial at boot:  
> `BLE MAC: XX:XX:XX:XX:XX:XX`  
> Update `DEVICE_MAC` in the Python scripts accordingly.

### Simulation & GUI

Located in `v_env/`. Requires `pygame` and `bleak`.

| Script | Purpose |
| :--- | :--- |
| `brody_sim_main.py` | **Main demo simulation.** Spiral threats approach across escalating waves; merges Ashlynn's wave logic with Brody's UI. Used during the live demo. |
| `gui_update_on_event.py` | **Interactive debug / intro tool.** Click to place threats, drag to reposition, right-click to remove. Sector wheel visualization shows motor mapping. Good for introducing a user to the system. |
| `gui_ashlynn_sim.py` | Game-mode simulation with 4 escalating waves and lock-on neutralization mechanic. |
| `gui_drag_and_drop.py` | Simple drag-and-drop threat placement GUI. |
| `gui_single.py` | Single-threat GUI with BLE. |
| `gui_mult.py` | Multi-threat GUI with BLE. |
| `gui_varforce.py` | Multi-threat with variable force GUI. |
| `gui_update_continously.py` | Continuous-update threat visualization with sector wheel. |

All simulation scripts connect to the belt automatically by scanning for a device named `"Argon"`.

**Controls (simulation scripts):**
- `SPACE` — start / restart simulation
- `← →` arrow keys — rotate heading manually (when BLE is not connected)

---

## IMU Orientation Notes

The BNO085 reports orientation relative to its default flat-mount frame. The firmware corrects for the physical mounting orientation of the board on the belt via a configurable initial quaternion passed to `BeltIMU::setup()`:

```cpp
// HapticBelt.cpp — adjust to match your board mounting angle
Quat initialOrientation{sqrt(2)/2, 0, sqrt(2)/2, 0};
IMUHandler.setup(initialOrientation);
```

To find the right quaternion for a new mounting orientation:
1. Orient the belt as you want "forward" to be.
2. Read the raw quaternion over Serial.
3. Pass that quaternion as `initialOrientation`.

The IMU module also handles sensor resets transparently: it computes a continuity-preserving offset quaternion so the heading does not jump when the BNO085 resets mid-session.

---

## Haptic Rendering

Motor index 0 corresponds to "forward" (front of the belt). Motors are numbered 0–7 clockwise when viewed from above.

For each active threat:
1. Compute target azimuth: `-(atan2(y, x) × 180/π − 90°)` — converts from standard math to compass convention (0° = forward, clockwise positive)
2. Subtract current yaw to get relative bearing, normalized to (−180°, +180°]
3. Map bearing to nearest motor index (45° sectors)
4. Scale intensity: `intensity = clamp(1 − range/400, 0.1, 1.0)`

Each threat slot (0–9) is assigned a unique **haptic signature** — a temporal on/off vibration pattern defined in `HapticSignature`. This allows the operator to distinguish between multiple simultaneous threats by feel. The motor only fires when the threat's signature is in its "active" phase.

---

## Analysis & Simulation

We also model the mechanical dynamics of the belt for design optimization:

**`Analysis/Analysis.m`** (MATLAB) — 2-DOF mass-spring-damper model comparing vibration response of an unconstrained belt vs. a belt worn on a person. Models ERM forcing and housing dynamics.

---

## License

MIT License
ME327 Academic Project, Stanford University, Spring 2026.
