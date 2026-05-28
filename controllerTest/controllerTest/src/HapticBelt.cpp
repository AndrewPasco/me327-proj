#include "HapticBelt.h"
#include <math.h>

HapticBelt::HapticBelt() {}

HapticBelt::~HapticBelt() {}

void HapticBelt::setup() {
    // pass the threat tracker's callback function for data reception to BLE handler
    BLEHandler.setup(ThreatTracker::rx_callback, &(this->ThreatTrack));    
    
    Quat initialOrientation{sqrt(2)/2,0,sqrt(2)/2,0};
    IMUHandler.setup(initialOrientation);
    
    motorDriver.setup();

    pinMode(light,OUTPUT);
}

void HapticBelt::loop() {
    digitalWrite(light,HIGH);
    delay(50);
    digitalWrite(light,LOW);
    delay(50);

    // Grab quaternion from IMU
    IMUHandler.check_connection();
    Quat orientation = IMUHandler.get_quaternion();
    
    // Convert to Euler Yaw
    float siny_cosp = 2.0f * (orientation.w * orientation.z + orientation.x * orientation.y);
    float cosy_cosp = 1.0f - 2.0f * (orientation.y * orientation.y + orientation.z * orientation.z);
    float yaw = -atan2(siny_cosp, cosy_cosp) * 180.0f / M_PI;  // negate to match compass convention (clockwise positive)
    
    // Parse received string threats
    ThreatTrack.update();

    // Render to motors
    renderHaptics(yaw);

    // transmit orientation quaternion via BLE
    BLEHandler.transmit_orientation(orientation.w, orientation.x, orientation.y, orientation.z);
}

float normalizeAngle(float angle) {
    angle = fmod(angle, 360.0f);
    if (angle < 0) {
        angle += 360.0f;
    }
    return angle;
}

void HapticBelt::renderHaptics(float currentRelativeYaw) {
    Threat* activeThreats[10];
    int count = ThreatTrack.getActiveThreats(activeThreats, 10);
    
    if (count == 0) {
        motorDriver.stopAllMotors();
        return;
    }
    
    motorDriver.stopAllMotors();
    
    float sectorSize = 360.0f / 8.0f;


    for (int i = 0; i < count; i++) {
        float x = activeThreats[i]->coords[0];
        float y = activeThreats[i]->coords[1];
        
        // +x is right, +y is up (forward in python GUI)
        // atan2(x,y) gives 0 for y-axis, positive for x-axis -> maps to azimuth
        float targetAzimuth = -(atan2(y, x) * 180.0f / M_PI - 90.0f);
        Serial.println(targetAzimuth);
        float error = targetAzimuth - currentRelativeYaw;
        error = fmod(error + 540.0f, 360.0f) - 180.0f; 

        int motorIndex = round(normalizeAngle(error) / sectorSize);
        if (motorIndex == 8) motorIndex = 0; // Wrap around

        // Scale intensity inversely by distance
        float range = sqrt(x*x + y*y);
        float intensity = constrain(1.0f - (range / 400.0f), 0.1f, 1.0f);

        if ((activeThreats[i]->signature).is_active()) {
            motorDriver.triggerMotor(motorIndex, intensity);
        }
        
    }
}