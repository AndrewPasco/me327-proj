#include "ThreatTracker.h"



ThreatTracker::ThreatTracker() {
    // initialize signatures
    struct signature
    {
        unsigned long* data;
        size_t len;
    };
    #define ARRAY_LEN(x) (sizeof(x) / sizeof((x)[0]))

    unsigned long sig0[] = {};
    unsigned long sig1[] = {};
    unsigned long sig2[] = {};
    unsigned long sig3[] = {};
    unsigned long sig4[] = {};
    unsigned long sig5[] = {};
    unsigned long sig6[] = {};
    unsigned long sig7[] = {};
    unsigned long sig8[] = {};
    unsigned long sig9[] = {};
    size_t numSigs = 20;
    signature sigs[numSigs] = 
    {
        {sig0, ARRAY_LEN(sig0)},
        {sig1, ARRAY_LEN(sig0)},
        {sig2, ARRAY_LEN(sig0)},
        {sig3, ARRAY_LEN(sig0)},
        {sig4, ARRAY_LEN(sig0)},
        {sig5, ARRAY_LEN(sig0)},
        {sig6, ARRAY_LEN(sig0)},
        {sig7, ARRAY_LEN(sig0)},
        {sig8, ARRAY_LEN(sig0)},
        {sig9, ARRAY_LEN(sig0)},
    };
    
    for (size_t i = 0; i < 10;i++) {
        Threats[0].signature = HapticSignature(sigs[i].data, sigs[i].len);
    }
    
}

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
        if (messageCount >= messageBufferSize) {
            Serial.println("Error: message buffer overflow");
        } else {
            byteStringBuffer[messageCount] = buffer;
            messageCount++;
        }
    }
    Serial.println(buffer);
}

void ThreatTracker::update() {
    String localStrArray[10];
    size_t numMessages = 0;


    WITH_LOCK(dataMutex) {
        if (messageCount > 0) {
            numMessages = messageCount;
            // need to loop through the array to 
            // enforce deep copy, kinda dumb
            for (size_t i = 0; i < numMessages; i++) {
                localStrArray[i] = byteStringBuffer[i];
            }
            messageCount = 0; // clear after reading
        }
    }
    
    if (numMessages == 0) return;

    for (size_t i = 0; i < numMessages; i++) {
        String localStr = localStrArray[i];

        // Parse semicolon separated threats
        unsigned int startIdx = 0;
        while (startIdx < localStr.length()) {
            int endIdx = localStr.indexOf(';', startIdx);
            if (endIdx == -1) endIdx = localStr.length();
            
            String threatStr = localStr.substring(startIdx, endIdx);
            startIdx = endIdx + 1;
            
            if (threatStr.length() == 0) continue;
            
            // Parse id, x, y, z
            int id;
            float x, y;
            int z;
            if (sscanf(threatStr.c_str(), "%d,%f,%f,%d", &id, &x, &y, &z) == 4) {
                
                // Find existing threat slot, or an empty slot
                int targetIdx = -1;
                int emptyIdx = -1;
                
                for (int i = 0; i < maxThreats; i++) {
                    if (Threats[i].active && Threats[i].id == id) {
                        targetIdx = i; // Found existing
                        break;
                    }
                    if (!Threats[i].active && emptyIdx == -1) {
                        emptyIdx = i; // Found first empty
                    }
                }
                
                if (z == -1) {
                    // Remove threat
                    if (targetIdx != -1) {
                        Threats[targetIdx].active = false;
                    }
                } else {
                    // Add or update threat
                    if (targetIdx == -1) {
                        targetIdx = emptyIdx; // Use empty slot if new
                    }
                    
                    if (targetIdx != -1) { // If we found a valid slot
                        Threats[targetIdx].id = id;
                        Threats[targetIdx].active = true;
                        Threats[targetIdx].coords[0] = x;
                        Threats[targetIdx].coords[1] = y;
                        Threats[targetIdx].coords[2] = z;
                    } else {
                        Serial.println("Warning: Max threats reached, dropping threat");
                    }
                }
            }
        }
    }
}

int ThreatTracker::getActiveThreats(Threat* activeList[], int maxListSize) {
    int count = 0;
    for (int i = 0; i < maxThreats && count < maxListSize; i++) {
        if (Threats[i].active) {
            activeList[count++] = &Threats[i];
        }
    }
    return count;
}