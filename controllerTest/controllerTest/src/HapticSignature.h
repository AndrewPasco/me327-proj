#include "particle.h"


class HapticSignature {
public:
    HapticSignature() {
        this->length = 0;
    }
    HapticSignature(unsigned long switchTimes[], size_t length) {
        
        if (length > MAX_SIGNATURE_LENGTH) {
            Serial.println("Error: haptic signature length too long");
            this->length = 0;
            return;
        }

        this->length = length;
        for (size_t i = 0; i < length; i++) {
            this->switchTimes[i] = switchTimes[i];
        }

        // start the switching
        currIdx = 0;
        isActive = true;
        unsigned long currTime = millis();
        nextSwitch = this->switchTimes[currIdx] + currTime;
    }

    bool is_active() {
        // a signature with 0 length is just always on
        if (length == 0) {
            return true;
        }

        unsigned long currTime = millis();
        // switching logic
        if (currTime > nextSwitch) {
            isActive = !isActive;
            currIdx = (currIdx+1)%length;
            nextSwitch = switchTimes[currIdx] + currTime;
        }
        return isActive;
    }
private:
    static const size_t MAX_SIGNATURE_LENGTH = 10;
    unsigned long switchTimes[MAX_SIGNATURE_LENGTH];
    size_t length;

    bool isActive;
    size_t currIdx;
    unsigned long nextSwitch;
};