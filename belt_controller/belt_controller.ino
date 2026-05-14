#include "Adafruit_BNO08x_RVC.h"

Adafruit_BNO08x_RVC rvc = Adafruit_BNO08x_RVC();

// --- Configuration ---
const unsigned long IMU_TIMEOUT_MS = 100; // Time before considering IMU disconnected
const unsigned long TELEMETRY_INTERVAL_MS = 100; // Interval for sending data back to host (Currently 10Hz)

// --- State Variables ---
float currentYawRaw = 0.0;
float referenceYaw = 0.0;
unsigned long lastImuUpdate = 0;
unsigned long lastTelemetrySend = 0;
bool imuConnected = false;

// --- Placeholders for BLE and Motors --- NOT IMPLEMENTED YET
void triggerMotor(int motorIndex, float intensity) {
  // Placeholder: Map motorIndex to a PWM pin and write intensity
}

void stopAllMotors() {
  // Placeholder: set all motor PWMs to 0, eg when we want to reset or disable active threats
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

// Processes a threat received from the host
void onThreatReceived(float targetAzimuth, float intensity) {
  float currentRelativeYaw = getHeading();
  
  // Calculate shortest path error
  float error = targetAzimuth - currentRelativeYaw;
  // Normalize error to [-180, 180) to find the closest direction
  error = fmod(error + 540.0, 360.0) - 180.0; 

  Serial.print("Threat received: "); Serial.print(targetAzimuth);
  Serial.print(" | Error: "); Serial.println(error);

  // Map error to 8 motors (45 degrees per motor)
  // Motor 0 is Front (0 degrees), Motor 1 is Front-Right (45 degrees), etc.
  float sectorSize = 360.0 / 8.0;
  // Shift by half a sector so the threshold is between motors
  int motorIndex = round(normalizeAngle(error) / sectorSize);
  if (motorIndex == 8) motorIndex = 0; // Wrap around

  triggerMotor(motorIndex, intensity);
}

// --- Setup and Loop ---

void setup() {
  Serial.begin(115200);
  
  // Start hardware serial for BNO08x (RX: D10, TX: D9 on Argon usually)
  Serial1.begin(115200); 

  Serial.println("Haptic Belt - State Estimation Init");

  if (!rvc.begin(&Serial1)) { 
    Serial.println("WARNING: Could not find BNO08x at startup!");
    // We don't block here. We let the loop handle reconnection/timeouts.
  } else {
    Serial.println("BNO08x initialized.");
    imuConnected = true;
  }

  // Initialize motors here...
  stopAllMotors();
}

void loop() {
  unsigned long currentMillis = millis();

  // 1. Process IMU Data (Non-blocking)
  BNO08x_RVC_Data headingData;
  if (rvc.read(&headingData)) {
    currentYawRaw = headingData.yaw;
    lastImuUpdate = currentMillis;
    if (!imuConnected) {
      Serial.println("IMU Connection Recovered!");
      imuConnected = true;
    }
  }

  // 2. Check IMU Health
  if (imuConnected && (currentMillis - lastImuUpdate > IMU_TIMEOUT_MS)) {
    Serial.println("ERROR: IMU Data Timeout! Lost connection.");
    imuConnected = false;
    stopAllMotors(); // Safety: stop haptics if we lose orientation
  }

  // 3. Simulated Host Input (Replace with BLE loop)
  // Periodically pretend we get a threat at 90 degrees (East relative to reference)
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'c') { // Type 'c' in serial to calibrate/zero
      setReference();
    } else if (cmd == 't') { // Type 't' to simulate a threat
      onThreatReceived(90.0, 1.0); // Threat at 90 deg, max intensity
    }
  }

  // 4. Send Telemetry
  if (currentMillis - lastTelemetrySend > TELEMETRY_INTERVAL_MS) {
    if (imuConnected) {
      sendTelemetry(getHeading());
    }
    lastTelemetrySend = currentMillis;
  }
}
