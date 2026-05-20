## ME327 Haptic Belt Requirements and Proposed Code Architecture
This document includes the requirements for the haptic belt code and a proposed code architecture for achieving these reqs.

### Requirements

1. Receive incoming local frame "detections" (as if they have been detected by a device worn by the operator) via BLE from the "host computer"
    - Determine relative threat vector. Based on relative threat vector, determine appropriate motor(s) which should be activated and their associated duty cycle(s).
    - Update relative threat vector as operator continues to move / yaw
2. Process incoming data from BNO085 IMU
    - Calibration routine to align local 0 yaw to a global frame?
3. Stream yaw back to host computer for rendering?
4. Manage PWM signals to the 8 ERM based on detected threats.

### Relevant System Details

Main processor: Particle Argon with Nordic Semiconductor nRF52840 SoC
- ARM Cortex-M4F 32-bit processor @ 64MHz
- 1MB flash, 256KB RAM
- Bluetooth LE (BLE) central and peripheral support
- 20 mixed signal GPIO (6 x Analog, 8 x PWM), UART, I2C, SPI
- Supports DSP instructions, HW accelerated Floating Point Unit (FPU) and encryption functions
- Up to +8 dBm TX power (down to -20 dBm in 4 dB steps)
- NFC-A radio
- 12 PWM compatible pins, broken into three groups of four which can have different duty cycles on the same frequency

IMU Fusion Breakout Board: BNO085
- Acceleration Vector / Accelerometer
- Angular Velocity Vector / Gyro
- Magnetic Field Strength Vector / Magnetometer
- Linear Acceleration Vector
- Gravity Vector
- Absolute Orientation/  Rotation Vector
    - Four point quaternion output for accurate data manipulation
- Application Optimized Rotation Vectors

### Proposed Architecture

#### 1. Coordinate Frames
To ensure the belt correctly maps threats as the user turns, we define three frames:
*   **Global Frame ($G$):** Fixed to the world (e.g., North/East/Down). 
*   **Reference Frame ($R$):** The "Zero" orientation established at calibration or power-on.
*   **Body Frame ($B$):** The current orientation of the belt/user.
*   **Threat Vector ($\vec{T}$):** Received from the host as an azimuth relative to the Global or Reference frame (to be determined, we could honestly do either).

#### 2. Software Modules

| Module | Responsibility |
| :--- | :--- |
| **IMU Manager** | Interfaces with BNO08x via UART-RVC. Handles yaw zeroing (re-centering) and smoothing. Maintains internal orientation state. |
| **BLE Comms** | Manages the BLE peripheral. Receives threat packets (Threat ID, Azimuth/Bearing, Range/Intensity) via callbacks to update the Threat Manager. Sends current Heading back to the host on a fixed interval. |
| **Threat Manager** | Data structure/class that manages a collection of active threats (bearing, range). Provides callbacks to add, update, or remove threats based on incoming BLE data. |
| **Haptic Renderer** | Called each execution of the main loop. Examines the active threats in the Threat Manager and the current orientation from the IMU Manager. Determines which motors should buzz and how, then passes this to the Haptic Driver. |
| **Haptic Driver** | Translates abstract haptic commands (from the Renderer) into physical PWM signals for the motors. |

#### 3. Data Flow
1.  **IMU Manager** updates `current_yaw` at 100Hz based on incoming signal from IMU.
2.  **BLE Comms** receives a threat packet (ID, Bearing, Range) from the host and triggers a callback on the **Threat Manager**.
3.  **Threat Manager** adds or updates the threat in its internal state. Stale threats may be pruned.
4.  In the main loop, the **Haptic Renderer** gets the active threats and `current_yaw`. It calculates the relative error ($Azimuth_{Relative} = Azimuth_{Target} - Heading_{Current}$) for each threat and decides the combined motor actuation strategy.
5.  **Haptic Driver** applies the calculated PWM signals to the selected motors
6.  **BLE Comms** periodically sends `current_yaw` back to the host for 2D visualization/sync.

#### 4. Interfaces (Abstractions)

```cpp
// IMU Interface
float getHeading();       // Returns 0-360 relative to reference
void setReference();      // Zeros the current yaw

// Threat Manager Interface
struct Threat {
    uint8_t id;
    float bearing;
    float range;
    unsigned long lastUpdated;
};

class ThreatManager {
public:
    void addOrUpdateThreat(uint8_t id, float bearing, float range);
    void removeThreat(uint8_t id);
    void cleanupStaleThreats(unsigned long timeout);
    int getActiveThreatCount();
    Threat getThreat(int index);
};

// Haptic Renderer Interface
void renderHaptics(ThreatManager& tm, float currentYaw);

// Haptic Driver Interface
void triggerMotor(int motorIndex, float intensity);
void stopAllMotors();
```

### Proposed Hardware Mapping (Argon)
*   **IMU (UART1):** RX -> D10/RX, TX -> D9/TX (using hardware Serial1)
*   **Motors (PWM):** Using 8 pins from the D2-D8 and A0-A5 pool. (e.g., D2, D3, D4, D5, D6, D7, D8, A0)
*   **Status LED:** On-board D7 (avoiding using D7 for motors if using onboard LED for status)