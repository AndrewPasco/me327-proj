#pragma once
#include "Particle.h"

class MotorDriver
{
public:
    MotorDriver();
    ~MotorDriver();

    void setup();
    void triggerMotor(int motorIndex, float intensity);
    void stopAllMotors();

private:
    static const int MOTOR_COUNT = 8;
    static const int PWM_FREQUENCY = 500;
    // Real Argon pins
    const int motorPins[8] = {D5, D4, D8, D6, A1, A2, A4, A5};
};
// 1   4    3   5   6   7   8  2  
// A1, A2, A4, A5, D4, D5, D6, D8

// A1, D8, A4, A2, A5, D4, D5, D6
// A1, D6, D5, D4, A5, A2, A4, D8


// A1, A2, A4, A5, D4, D5, D6, D8
// A1, D8, D8, A2, A4, A5, D4, D6

// D6, D4, A5, A4, A2, D8, D8, A1