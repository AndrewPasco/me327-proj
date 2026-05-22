# pragma once

#include "BeltBLE.h"
#include "ThreatTracker.h"
#include "BeltIMU.h"

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

    const int light = D7;
};