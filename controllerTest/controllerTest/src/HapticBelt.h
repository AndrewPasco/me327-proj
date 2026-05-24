# pragma once

#include "BeltBLE.h"
#include "ThreatTracker.h"
#include "BeltIMU.h"
#include "MotorDriver.h"

class HapticBelt
{
public:
    HapticBelt();
    ~HapticBelt();
    void setup();
    void loop();
private:
    ThreatTracker ThreatTrack;
    BeltBLE BLEHandler;
    BeltIMU IMUHandler;
    MotorDriver motorDriver;

    const int light = D7;

    void renderHaptics(float currentRelativeYaw);
};