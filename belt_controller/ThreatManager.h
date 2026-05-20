#ifndef THREAT_MANAGER_H
#define THREAT_MANAGER_H

#include <Arduino.h>

#define MAX_THREATS 10

struct Threat {
    uint8_t id;
    float bearing;
    float range; // Or intensity
    unsigned long lastUpdated;
    bool active;
};

class ThreatManager {
private:
    Threat threats[MAX_THREATS];

public:
    ThreatManager() {
        for (int i = 0; i < MAX_THREATS; i++) {
            threats[i].active = false;
        }
    }

    void addOrUpdateThreat(uint8_t id, float bearing, float range) {
        // Try to update existing threat
        for (int i = 0; i < MAX_THREATS; i++) {
            if (threats[i].active && threats[i].id == id) {
                threats[i].bearing = bearing;
                threats[i].range = range;
                threats[i].lastUpdated = millis();
                return;
            }
        }

        // Otherwise, find an empty slot
        for (int i = 0; i < MAX_THREATS; i++) {
            if (!threats[i].active) {
                threats[i].id = id;
                threats[i].bearing = bearing;
                threats[i].range = range;
                threats[i].lastUpdated = millis();
                threats[i].active = true;
                return;
            }
        }
    }

    void removeThreat(uint8_t id) {
        for (int i = 0; i < MAX_THREATS; i++) {
            if (threats[i].active && threats[i].id == id) {
                threats[i].active = false;
                return;
            }
        }
    }

    void cleanupStaleThreats(unsigned long timeoutMillis) {
        unsigned long currentMillis = millis();
        for (int i = 0; i < MAX_THREATS; i++) {
            if (threats[i].active && (currentMillis - threats[i].lastUpdated > timeoutMillis)) {
                threats[i].active = false;
            }
        }
    }

    int getActiveThreatCount() {
        int count = 0;
        for (int i = 0; i < MAX_THREATS; i++) {
            if (threats[i].active) {
                count++;
            }
        }
        return count;
    }

    // Fills an array of pointers with active threats to avoid copying
    int getActiveThreats(Threat* activeList[], int maxListSize) {
        int count = 0;
        for (int i = 0; i < MAX_THREATS && count < maxListSize; i++) {
            if (threats[i].active) {
                activeList[count++] = &threats[i];
            }
        }
        return count;
    }
};

#endif // THREAT_MANAGER_H
