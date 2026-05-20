#include "Particle.h"
#include "Adafruit_BNO08x_RVC.h"
#include "ThreatManager.h"

// --- System Configuration ---
// MANUAL mode: no WiFi/Cloud, BLE only: faster boot, lower power
SYSTEM_MODE(MANUAL);
// BLE callbacks run on a separate OS thread; shared state must be mutex-protected
SYSTEM_THREAD(ENABLED);

// Thread-safe logging (Serial.print is NOT safe with SYSTEM_THREAD)
SerialLogHandler logHandler(LOG_LEVEL_INFO);

// --- BLE Configuration ---
// Service UUID (unchanged from controllerTest for Python compatibility)
BleUuid beltServiceUuid("62c3cf89-247b-4c0f-a70d-651080844609");
// RX UUID:
BleUuid threatRxUuid("62c3cf89-247b-4c0f-a70d-651080844607");
// TX UUID (unchanged from controllerTest for Python compatibility)
BleUuid telemetryTxUuid("62c3cf89-247b-4c0f-a70d-651080844608");

// Forward-declare BLE callback
void onBleDataReceived(const uint8_t* data, size_t len,
    const BlePeerDevice& peer, void* context);

// TX: Belt → Host telemetry (NOTIFY)
BleCharacteristic telemetryChar("Telemetry",
    BleCharacteristicProperty::NOTIFY, telemetryTxUuid, beltServiceUuid);

// RX: Host → Belt threat messages (WRITE_WO_RSP)
BleCharacteristic threatRxChar("ThreatRx",
    BleCharacteristicProperty::WRITE_WO_RSP, threatRxUuid, beltServiceUuid,
    onBleDataReceived, NULL);

// --- BLE Thread-Safe Shared State ---

/**
 * Binary message format for incoming threats over BLE.
 * 9 bytes, packed, little-endian.
 *
 * Python packing:  struct.pack('<Bff', id, bearing, range)
 *
 * Semantics:
 *   - New ID       → add to threat list
 *   - Existing ID  → update bearing/range
 *   - range == 0.0 → remove threat
 *
 * One message per BLE write. For multiple threats, the host sends
 * successive writes (handled on the Python side).
 */
struct __attribute__((packed)) ThreatMessage {
    uint8_t id;
    float bearing;
    float range;
};

// Ring buffer: BLE thread produces, loop() consumes
const int PENDING_BUFFER_SIZE = 8;
volatile int pendingWriteIdx = 0;
volatile int pendingReadIdx = 0;
ThreatMessage pendingThreats[PENDING_BUFFER_SIZE];
Mutex threatMutex;

// --- IMU ---
Adafruit_BNO08x_RVC rvc = Adafruit_BNO08x_RVC();

// --- Configuration ---
const unsigned long IMU_TIMEOUT_MS = 100; // Time before considering IMU disconnected
const unsigned long TELEMETRY_INTERVAL_MS = 100; // Interval for sending data back to host (Currently 10Hz)
const unsigned long THREAT_TIMEOUT_MS = 20000; // Time before a threat is considered stale (20s)
const int PWM_FREQUENCY = 500; // Maximum possible (also default)

// --- State Variables ---
float currentYawRaw = 0.0;
float referenceYaw = 0.0;
unsigned long lastImuUpdate = 0;
unsigned long lastTelemetrySend = 0;
bool imuConnected = false;

// --- Threat Manager ---
ThreatManager threatManager;

// --- Hardware Pins ---
// Map the 8 motors to specific pins on the Particle Argon
const int MOTOR_COUNT = 8;
const int motorPins[MOTOR_COUNT] = {
  A0, // Motor 0: Front (0 deg)
  A1, // Motor 1: Front-Right (45 deg)
  A2, // Motor 2: Right (90 deg)
  A3, // Motor 3: Back-Right (135 deg)
  D4, // Motor 4: Back (180 deg)
  D5, // Motor 5: Back-Left (225 deg)
  D6, // Motor 6: Left (270 deg)
  D8  // Motor 7: Front-Left (315 deg)
};

// =============================================================================
// BLE Callback (runs on BLE OS thread — keep minimal and non-blocking!)
// =============================================================================

/**
 * Called by the BLE stack when the host writes to the ThreatRx characteristic.
 * Copies the raw bytes into the ring buffer and returns immediately.
 * All parsing, threat management, and logging happens in loop().
 *
 * IMPORTANT: Do NOT call Serial.print, Particle.publish, or any blocking
 * function from this callback. Use Log.trace at most for lightweight debug.
 */
void onBleDataReceived(const uint8_t* data, size_t len,
    const BlePeerDevice& peer, void* context)
{
  // Validate message size — expect exactly one ThreatMessage per write
  if (len != sizeof(ThreatMessage)) return;

  WITH_LOCK(threatMutex) {
    int nextWrite = (pendingWriteIdx + 1) % PENDING_BUFFER_SIZE;
    if (nextWrite != pendingReadIdx) { // Buffer not full
      memcpy(&pendingThreats[pendingWriteIdx], data, sizeof(ThreatMessage));
      pendingWriteIdx = nextWrite;
    }
    // If buffer is full, silently drop (non-blocking, no allocation)
  }
}

// =============================================================================
// Motor Logic
// =============================================================================

/**
 * Triggers a specific motor with a given intensity.
 * @param motorIndex: 0-7
 * @param intensity: 0.0 (off) to 1.0 (max)
 */
void triggerMotor(int motorIndex, float intensity) {
  if (motorIndex < 0 || motorIndex >= MOTOR_COUNT) return;
  
  // Constrain intensity and map to 8-bit PWM (0-255)
  int pwmValue = (int)(constrain(intensity, 0.0, 1.0) * 255);
  
  analogWrite(motorPins[motorIndex], pwmValue);
}

/**
 * Sets all motor PWMs to 0.
 */
void stopAllMotors() {
  for (int i = 0; i < MOTOR_COUNT; i++) {
    analogWrite(motorPins[i], 0);
  }
}

// =============================================================================
// Telemetry
// =============================================================================

/**
 * Sends a telemetry update to the host over BLE (NOTIFY characteristic).
 * Format: "YAW,<heading>,IMU,<0|1>"
 *   - YAW: relative heading in degrees (float, 2 decimal places)
 *   - IMU: 1 if IMU is connected, 0 otherwise
 */
void sendTelemetry(float relativeYaw) {
  char buf[48];
  snprintf(buf, sizeof(buf), "YAW,%.2f,IMU,%d",
           relativeYaw, imuConnected ? 1 : 0);
  telemetryChar.setValue(buf);
  Log.trace("Telemetry -> %s", buf);
}

// =============================================================================
// Core Logic
// =============================================================================

// Normalizes an angle to the [0, 360) range
float normalizeAngle(float angle) {
  angle = fmod(angle, 360.0);
  if (angle < 0) {
    angle += 360.0;
  }
  return angle;
}

// Zeros the heading to the current physical orientation
void setReference() {
  referenceYaw = currentYawRaw;
  Log.info("Reference set to: %.2f", referenceYaw);
}

// Returns the heading relative to the set reference
float getHeading() {
  return normalizeAngle(currentYawRaw - referenceYaw);
}

/**
 * Drains the ring buffer of pending threat messages from BLE.
 * Called from loop() — safe to do heavy work here (logging, ThreatManager updates).
 */
void processPendingThreats() {
  WITH_LOCK(threatMutex) {
    while (pendingReadIdx != pendingWriteIdx) {
      ThreatMessage msg = pendingThreats[pendingReadIdx];
      pendingReadIdx = (pendingReadIdx + 1) % PENDING_BUFFER_SIZE;

      if (msg.range == 0.0f) {
        threatManager.removeThreat(msg.id);
        Log.info("Threat removed - ID: %d", msg.id);
      } else {
        threatManager.addOrUpdateThreat(msg.id, msg.bearing, msg.range);
        Log.info("Threat updated - ID: %d, Az: %.1f, Range: %.1f",
                 msg.id, msg.bearing, msg.range);
      }
    }
  }
}

// Haptic Renderer: determines motor activations based on active threats and current yaw
void renderHaptics() {
  float currentRelativeYaw = getHeading();
  
  // Clean up any old threats
  threatManager.cleanupStaleThreats(THREAT_TIMEOUT_MS);
  
  int activeCount = threatManager.getActiveThreatCount();
  if (activeCount == 0) {
    stopAllMotors();
    return;
  }
  
  Threat* activeThreats[MAX_THREATS];
  int count = threatManager.getActiveThreats(activeThreats, MAX_THREATS);

  // Stop all motors first, then trigger only the needed ones.
  stopAllMotors();
  
  float sectorSize = 360.0 / 8.0;

  for (int i = 0; i < count; i++) {
    float targetAzimuth = activeThreats[i]->bearing;
    float intensity = activeThreats[i]->range; // For now, use range as intensity or map inversely
    
    // Calculate shortest path error
    float error = targetAzimuth - currentRelativeYaw;
    // Normalize error to [-180, 180) to find the closest direction
    error = fmod(error + 540.0, 360.0) - 180.0; 

    // Shift by half a sector so the threshold is between motors
    int motorIndex = round(normalizeAngle(error) / sectorSize);
    if (motorIndex == 8) motorIndex = 0; // Wrap around

    triggerMotor(motorIndex, intensity);
  }
}

// =============================================================================
// Setup and Loop
// =============================================================================

void setup() {
  Serial.begin(115200);
  
  // Start hardware serial for BNO08x (Board RX to BNO085 SDA)
  Serial1.begin(115200); 

  Log.info("Haptic Belt - BLE + State Estimation Init");

  // --- IMU Init ---
  if (!rvc.begin(&Serial1)) { 
    Log.warn("Could not find BNO08x at startup!");
    // We don't block here. We let the loop handle reconnection/timeouts.
  } else {
    Log.info("BNO08x initialized.");
    imuConnected = true;
  }

  // --- Motor Init ---
  for (int i = 0; i < MOTOR_COUNT; i++) {
    pinMode(motorPins[i], OUTPUT);
  }

  // Set PWM Frequencies for the Argon groups
  // analogWrite(pin, value, frequency) sets frequency for the entire group
  analogWrite(motorPins[0], 0, PWM_FREQUENCY); // Sets frequency for Group A0-A3
  analogWrite(motorPins[4], 0, PWM_FREQUENCY); // Sets frequency for Group D4, D5, D6, D8

  stopAllMotors();

  // --- BLE Init ---
  // In MANUAL mode, we must explicitly enable BLE
  BLE.on();

  BLE.addCharacteristic(telemetryChar);
  BLE.addCharacteristic(threatRxChar);

  BleAdvertisingData advData;
  advData.appendServiceUUID(beltServiceUuid);
  BLE.setDeviceName("Argon Test"); // Keep existing name for now
  BLE.advertise(&advData);

  Log.info("BLE advertising started (Service: %s)", 
           beltServiceUuid.toString().c_str());
}

void loop() {
  unsigned long currentMillis = millis();

  // --- Process IMU Data (Non-blocking) ---
  BNO08x_RVC_Data headingData;
  if (rvc.read(&headingData)) {
    currentYawRaw = headingData.yaw;
    lastImuUpdate = currentMillis;
    if (!imuConnected) {
      Log.info("IMU Connection Recovered!");
      imuConnected = true;
    }
  }

  // --- Check IMU Health ---
  if (imuConnected && (currentMillis - lastImuUpdate > IMU_TIMEOUT_MS)) {
    Log.error("IMU Data Timeout! Lost connection.");
    imuConnected = false;
    stopAllMotors(); // Safety: stop haptics if we lose orientation
  }

  // --- Process incoming BLE threat messages ---
  processPendingThreats();

  // --- Serial debug commands (keep for development) ---
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'c') { // Type 'c' in serial to calibrate/zero
      setReference();
    }
  }

  // --- Update Haptics based on state ---
  renderHaptics();

  // --- Send Telemetry ---
  if (currentMillis - lastTelemetrySend > TELEMETRY_INTERVAL_MS) {
    if (imuConnected) {
      sendTelemetry(getHeading());
    }
    lastTelemetrySend = currentMillis;
  }
}
