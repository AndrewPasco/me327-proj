#include "ThreatTracker.h"

// Callback function for Rx BLE 
// static
void ThreatTracker::rx_callback( const uint8_t* data,  
							size_t len,  
							const BlePeerDevice& peer,  
							void* context)
{  
    // type casting required for private member access
    // note that because this is a static method, self is not actually defined in this scope
    ThreatTracker* self = static_cast<ThreatTracker*>(context);  
    self->handle_rx(data, len, peer);  
}

// Wrapper for accessing private members
void ThreatTracker::handle_rx(const uint8_t* data,  
					size_t len,  
					const BlePeerDevice& peer){  
    // can access private members here 
    Serial.println("recieved"); 
    char buffer[64];
    // avoid overflowing the buffer  
    size_t copyLen = min(len, sizeof(buffer) - 1);
    // copy raw BLE bytes into char buffer  
    memcpy(buffer, data, copyLen); 

    // last byte of a c string must be the 0 byte
    buffer[copyLen] = '\0';

    WITH_LOCK(dataMutex) {
        byteString = buffer;
    }
    Serial.println(byteString);
}