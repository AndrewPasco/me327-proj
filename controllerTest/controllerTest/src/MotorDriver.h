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
    const int motorPins[8] = {A4, A5, D4, D5, D6, D8, D11, D12};
};