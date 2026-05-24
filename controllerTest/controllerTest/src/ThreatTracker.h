#pragma once
#include "Particle.h"


struct Threat {
    int id = -1;
    bool active = false;
    float coords[3] = {0,0,0};
};
class ThreatTracker
{
public:
    ThreatTracker(){};
    ~ThreatTracker(){};

    // parses the received byteString into the Threats array
    void update();

    // populates activeList with pointers to active threats
    int getActiveThreats(volatile Threat* activeList[], int maxListSize);

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
    volatile Threat Threats[maxThreats];
    
    String byteString = "";

	void handle_rx(const uint8_t* data,  
					size_t len,  
					const BlePeerDevice& peer);
	
};

