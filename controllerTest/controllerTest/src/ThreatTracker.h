#pragma once
#include "Particle.h"


struct Threat {
    bool active = false;
    float coords[3] = {0,0,0};
};
class ThreatTracker
{
public:
    ThreatTracker(){};
    ~ThreatTracker(){};

    // calculates relative position of all threats and calls motor driver to
    // appropriately render positions of threats
    void render_threats(const float (&quat)[4]){};

    // callback function to pass to BLE handler
    static void rx_callback( const uint8_t* data,  
							size_t len,  
							const BlePeerDevice& peer,  
							void* context);


private:
    // used to lock thread to allow safe read/write of shared data
    Mutex dataMutex;
    
    static const int maxThreats = 10;
    Threat Threats[maxThreats];
    
    String byteString = "";

	void handle_rx(const uint8_t* data,  
					size_t len,  
					const BlePeerDevice& peer);
	
};

