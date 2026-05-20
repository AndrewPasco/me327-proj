#pragma once
#include "Particle.h"

class ThreatTracker
{
public:
    ThreatTracker(){};
    ~ThreatTracker(){};

    // callback function to pass to BLE handler
    static void rx_callback( const uint8_t* data,  
							size_t len,  
							const BlePeerDevice& peer,  
							void* context);

private:
    // used to lock thread to allow safe read/write of shared data
    Mutex dataMutex;

    String byteString = "";

	void handle_rx(const uint8_t* data,  
					size_t len,  
					const BlePeerDevice& peer);
	
};