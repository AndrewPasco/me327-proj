#include "HapticBelt.h"

HapticBelt::HapticBelt() {}

HapticBelt::~HapticBelt() {}

void HapticBelt::setup() {
    // pass the threat tracker's callback function for data reception to BLE handler
    BLEHandler.setup(ThreatTracker::rx_callback, &(this->ThreatTrack));    
    
    Quat initialOrientation{sqrt(2)/2,0,sqrt(2)/2,0};
    IMUHandler.setup(initialOrientation);

    pinMode(light,OUTPUT);
}

void HapticBelt::loop() {
    static int i = 0;
    Serial.println("loop");
    digitalWrite(light,HIGH);
    delay(50);
    digitalWrite(light,LOW);
    delay(50);

    // Grab quaternion from IMU
    IMUHandler.check_connection();
    Quat orientation = IMUHandler.get_quaternion();

    // Pass quaternion to threat tracker to have it render threats

    // maybe just have the threat tracker return a vector of yaws to render?

    // transmit orientation quaternion via BLE
    
    BLEHandler.transmit_orientation(orientation.w,orientation.x,orientation.y,orientation.z);
    i++;
}