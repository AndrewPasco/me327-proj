#include "MotorDriver.h"

MotorDriver::MotorDriver() {}

MotorDriver::~MotorDriver() {}

void MotorDriver::setup() {
    for (int i = 0; i < MOTOR_COUNT; i++) {
        pinMode(motorPins[i], OUTPUT);
        // analogWrite(pin, value, frequency) sets the frequency for the entire group
        analogWrite(motorPins[i], 0, PWM_FREQUENCY); 
    }
    
    stopAllMotors();
}

void MotorDriver::triggerMotor(int motorIndex, float intensity) {
    if (motorIndex < 0 || motorIndex >= MOTOR_COUNT) return;
    int pwmValue = (int)(constrain(intensity, 0.0, 1.0) * 255);
    analogWrite(motorPins[motorIndex], pwmValue);
}

void MotorDriver::stopAllMotors() {
    for (int i = 0; i < MOTOR_COUNT; i++) {
        analogWrite(motorPins[i], 0);
    }
}
