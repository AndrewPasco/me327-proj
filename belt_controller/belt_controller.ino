#include "Adafruit_BNO08x_RVC.h"
#include "ThreatManager.h"

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

// --- Motor Logic ---

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

void sendTelemetry(float relativeYaw) {
  // Placeholder: Send data over BLE to the host computer
  Serial.print("Telemetry -> Relative Yaw: ");
  Serial.println(relativeYaw);
}

// --- Core Logic ---

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
  Serial.print("Reference set to: ");
  Serial.println(referenceYaw);
}

// Returns the heading relative to the set reference
float getHeading() {
  return normalizeAngle(currentYawRaw - referenceYaw);
}

// Simulated BLE Callback: Processes a threat received from the host
void onThreatReceived(uint8_t id, float targetAzimuth, float range) {
  threatManager.addOrUpdateThreat(id, targetAzimuth, range);
  Serial.print("Threat received/updated - ID: "); Serial.print(id);
  Serial.print(" | Azimuth: "); Serial.print(targetAzimuth);
  Serial.print(" | Range: "); Serial.println(range);
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

// --- Setup and Loop ---

void setup() {
  Serial.begin(115200);
  
  // Start hardware serial for BNO08x (Board RX to BNO085 SDA)
  Serial1.begin(115200); 

  Serial.println("Haptic Belt - State Estimation Init");

  if (!rvc.begin(&Serial1)) { 
    Serial.println("WARNING: Could not find BNO08x at startup!");
    // We don't block here. We let the loop handle reconnection/timeouts.
  } else {
    Serial.println("BNO08x initialized.");
    imuConnected = true;
  }

  // Initialize motors
  for (int i = 0; i < MOTOR_COUNT; i++) {
    pinMode(motorPins[i], OUTPUT);
  }

  // Set PWM Frequencies for the Argon groups
  // analogWrite(pin, value, frequency) sets frequency for the entire group
  analogWrite(motorPins[0], 0, PWM_FREQUENCY); // Sets frequency for Group A0-A3
  analogWrite(motorPins[4], 0, PWM_FREQUENCY); // Sets frequency for Group D4, D5, D6, D8

  stopAllMotors();
}

void loop() {
  unsigned long currentMillis = millis();

  // Process IMU Data (Non-blocking)
  BNO08x_RVC_Data headingData;
  if (rvc.read(&headingData)) {
    currentYawRaw = headingData.yaw;
    lastImuUpdate = currentMillis;
    if (!imuConnected) {
      Serial.println("IMU Connection Recovered!");
      imuConnected = true;
    }
  }

  // Check IMU Health
  if (imuConnected && (currentMillis - lastImuUpdate > IMU_TIMEOUT_MS)) {
    Serial.println("ERROR: IMU Data Timeout! Lost connection.");
    imuConnected = false;
    stopAllMotors(); // Safety: stop haptics if we lose orientation
  }

  // Simulated Host Input (Replace with actual BLE loop when ready)
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'c') { // Type 'c' in serial to calibrate/zero
      setReference();
    } else if (cmd == 't') { // Type 't' to simulate a threat
      onThreatReceived(1, 90.0, 1.0); // Threat ID 1, at 90 deg, max intensity
    } else if (cmd == 'r') {
      threatManager.removeThreat(1);
    }
  }

  // Update Haptics based on state
  renderHaptics();

  // Send Telemetry
  if (currentMillis - lastTelemetrySend > TELEMETRY_INTERVAL_MS) {
    if (imuConnected) {
      sendTelemetry(getHeading());
    }
    lastTelemetrySend = currentMillis;
  }
}
