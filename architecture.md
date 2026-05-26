## ME327 Haptic Belt — Requirements and Code Architecture

This document describes the requirements for the haptic belt firmware and the implemented code architecture.

---

### Requirements

1. Receive incoming local-frame threat detections (as if detected by a device worn by the operator) via BLE from the host computer.
   - Determine the relative threat vector. Based on the relative threat vector, determine which motor(s) should be activated and their associated duty cycles.
   - Update the relative threat vector as the operator moves / yaws.
2. Process incoming data from the BNO085 IMU.
   - Calibrate belt mounting orientation at startup (configurable initial quaternion).
   - Maintain continuous orientation estimate; recover gracefully from IMU resets.
3. Stream the current orientation quaternion back to the host computer for rendering / visualization.
4. Manage PWM signals to 8 ERM vibration motors based on detected threats.

---

### Relevant System Details

**Microcontroller:** Particle Argon (Nordic Semiconductor nRF52840 SoC)
- ARM Cortex-M4F @ 64 MHz, 1 MB flash, 256 KB RAM
- Bluetooth LE central and peripheral support
- 20 mixed-signal GPIO (6× Analog, 8× PWM), UART, I2C, SPI
- Hardware FPU; DSP instructions; AES encryption accelerator
- 12 PWM-compatible pins, organized in three groups of four (same frequency per group; independent duty cycles)

**IMU:** BNO085 (I2C, via Adafruit_BNO08x library, Sahagun fork)
- Reports used: `SH2_GAME_ROTATION_VECTOR` (absolute orientation quaternion)
- Quaternion re-orientation applied at startup; offset correction applied after any sensor reset

**Motor Drivers:** DRV8833 ×4, controlled via PWM

---

### Implemented Architecture

#### 1. Coordinate Frames

| Frame | Description |
| :--- | :--- |
| **Global Frame (G)** | Fixed to the world. Threat positions are expressed here (x, y, z coordinates received from host). |
| **Body Frame (B)** | The current orientation of the belt/user. |
| **Initial/Reference Orientation** | A configurable quaternion passed to `BeltIMU::setup()` representing where the IMU is considered "forward" relative to its flat-mount default. Currently set to `{√2/2, 0, √2/2, 0}` to account for board mounting angle. |

#### 2. Class Hierarchy & Responsibilities

```
HapticBelt          (top-level orchestrator)
├── BeltBLE         (BLE peripheral: Rx threat data, Tx orientation)
├── BeltIMU         (I2C IMU interface: quaternion + heading)
├── ThreatTracker   (parses BLE packets, maintains threat state)
└── MotorDriver     (PWM abstraction for 8 ERM motors)
```

| Class | File(s) | Responsibility |
| :--- | :--- | :--- |
| **HapticBelt** | `HapticBelt.h/.cpp` | Top-level orchestrator. Owns all subsystems. Calls `setup()` and `loop()`. Pulls quaternion from `BeltIMU`, converts to yaw, queries active threats from `ThreatTracker`, maps threats to motors, and transmits orientation back over BLE via `BeltBLE`. |
| **BeltBLE** | `BeltBLE.h/.cpp` | Manages the BLE peripheral. Registers custom GATT service with Rx (write-without-response) and Tx (notify) characteristics. Passes a callback+context to the Rx characteristic on setup. Provides `transmit_orientation(w,x,y,z)` to broadcast the current quaternion. |
| **BeltIMU** | `BeltIMU.h/.cpp` | Interfaces with the BNO085 via I2C. Applies an initial re-orientation quaternion at startup. Handles IMU resets by computing a continuity-preserving offset quaternion. Exposes `get_quaternion()` (relative to initial orientation) and `get_heading()` (yaw in degrees). |
| **ThreatTracker** | `ThreatTracker.h/.cpp` | Holds a fixed-size array of up to 10 `Threat` structs. Provides a static `rx_callback` (passed to `BeltBLE::setup`) that stores incoming BLE bytes behind a `Mutex`. `update()` parses the buffered string and adds/updates/removes threats. `getActiveThreats()` returns pointers to currently active threats. |
| **MotorDriver** | `MotorDriver.h/.cpp` | Abstracts PWM control for 8 motors at 500 Hz. Maps motor index 0–7 to Argon pins `{A1, A2, A4, A5, D4, D5, D6, D8}`. `triggerMotor(index, intensity)` writes a 0–255 PWM value; `stopAllMotors()` zeroes all channels. |

#### 3. Key Data Structures

```cpp
// BeltIMU.h
struct Quat {
    float w, x, y, z;
};
// Utility functions (free functions in BeltIMU.cpp):
Quat Qmultiply(const Quat& a, const Quat& b); // Hamilton product + normalize
Quat Qconj(const Quat& q);                     // Quaternion conjugate
Quat Qnormalize(Quat q);                        // Unit normalization
void printQuat(Quat q);                          // Serial debug print

// ThreatTracker.h
struct Threat {
    int   id     = -1;
    bool  active = false;
    float coords[3] = {0, 0, 0}; // x, y, z in host coordinate frame
};
```

#### 4. Data Flow (Main Loop)

```
setup():
  BeltBLE::setup(ThreatTracker::rx_callback, &ThreatTrack)
    └─ registers Rx/Tx GATT characteristics; begins BLE advertising

  BeltIMU::setup({√2/2, 0, √2/2, 0})
    └─ begin_I2C(), enable SH2_GAME_ROTATION_VECTOR report, store initQ

  MotorDriver::setup()
    └─ configure 8 PWM pins @ 500 Hz, zero all outputs

loop() [runs continuously]:
  1. BeltIMU::check_connection()
        └─ reconnects if needed; computes offset quaternion after any IMU reset

  2. BeltIMU::get_quaternion()
        └─ reads SH2 rotation vector → applies re-orientation (Qmultiply(raw, Qconj(initQ)))
           → applies continuity offset → returns finalQuat

  3. Convert quaternion → yaw (degrees) via standard Euler decomposition:
        yaw = atan2(2(w·z + x·y), 1 − 2(y² + z²)) × 180/π

  4. ThreatTracker::update()
        └─ safely copies buffered byteString (Mutex-protected)
           → parses semicolon-separated "id,x,y,z" tokens
           → z == -1 ⟹ deactivate; otherwise add/update threat

  5. HapticBelt::renderHaptics(yaw)
        a. getActiveThreats() → list of active Threat*
        b. For each threat:
             targetAzimuth = atan2(x, y) × 180/π   // +x right, +y forward
             error = targetAzimuth − yaw             // relative bearing to threat
             error normalized to (−180, +180]
             motorIndex = round(normalizeAngle(error) / 45°) mod 8
             range = √(x² + y²)
             intensity = clamp(1 − range/400, 0.1, 1.0)
             MotorDriver::triggerMotor(motorIndex, intensity)

  6. BeltBLE::transmit_orientation(w, x, y, z)
        └─ formats as "w,x,y,z" string → Tx NOTIFY characteristic
```

#### 5. BLE Protocol

| Direction | UUID | Format | Description |
| :--- | :--- | :--- | :--- |
| Host → Belt (Rx) | `...844609` | `"id,x,y,z[;id,x,y,z...]"` | Semicolon-separated threat packets. `z == -1` signals threat removal. |
| Belt → Host (Tx) | `...844608` | `"w,x,y,z"` | Current orientation quaternion, 2 decimal places, sent each loop. |

#### 6. Hardware Pin Mapping (Particle Argon)

| Resource | Pin(s) | Notes |
| :--- | :--- | :--- |
| **IMU (I2C)** | SDA / SCL (default I2C bus) | BNO085 via `Adafruit_BNO08x` |
| **Motors 0–3** | A1, A2, A4, A5 | DRV8833 PWM inputs |
| **Motors 4–7** | D4, D5, D6, D8 | DRV8833 PWM inputs |
| **Status LED** | D7 (onboard) | Blink each loop iteration |
| **PWM Frequency** | 500 Hz | Set via `analogWrite(pin, 0, 500)` in `MotorDriver::setup()` |

---

### Third-Party Dependencies

| Library | Version | Purpose |
| :--- | :--- | :--- |
| `Adafruit_BNO08x_Sahagun` | 1.2.6 | BNO085 I2C driver (forked for Particle compatibility) |
| `Adafruit_BusIO_Sahagun` | — | I2C/SPI bus abstraction (transitive dep) |
| `Adafruit_Unified_Sensor_Sahagun` | — | Unified sensor abstraction (transitive dep) |

Dependencies are declared in `controllerTest/project.properties` and bundled under `controllerTest/lib/`.

---

### Host-Side Tooling (Python)

Located in `controllerTest/` (project root):

| Script | Purpose |
| :--- | :--- |
| `bleakListener.py` | Connects to the Argon by MAC address, subscribes to the Tx characteristic (orientation), and prints received packets to stdout. Development/debug tool. |
| `bleakScanAndListen` | Scans for the Argon by device name (`"Argon Test"`) before connecting. |
| `bleakScanner` | Passive BLE scanner utility. |
| `serialListener.py` | Reads USB Serial output from the Argon for local debug without BLE. |

All Python scripts use `bleak` for BLE communication. Run with `uv run <script>` after adding `bleak` to the project via `uv add bleak`.