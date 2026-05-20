# pragma once

#include "BeltBLE.h"
#include "ThreatTracker.h"

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

    const int light = D7;
};