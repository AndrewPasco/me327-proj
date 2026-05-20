#include "HapticBelt.h"

HapticBelt::HapticBelt() {}

HapticBelt::~HapticBelt() {}

void HapticBelt::setup() {
    // pass the threat tracker's callback function for data reception to BLE handler
    BLEHandler.setup(ThreatTracker::rx_callback, &(this->ThreatTrack));    

    pinMode(light,OUTPUT);
}

void HapticBelt::loop() {
    static int i = 0;

    Serial.println("loop");
    digitalWrite(light,HIGH);
    delay(500);
    digitalWrite(light,LOW);
    delay(500);
    
    BLEHandler.transmit_orientation(i,1,2,3);
    i++;
}