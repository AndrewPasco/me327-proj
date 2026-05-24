// Simple Motor Testing Script for D11 and D12

// Note: Particle Argon pinouts typically don't label pins as D11/D12, 
// they are usually the SPI pins (MOSI, MISO) or labeled explicitly on custom boards.
// Ensure your board supports PWM on these pins!

const int MOTOR_1_PIN = D11;
const int MOTOR_2_PIN = D12;

const int PWM_FREQ = 500;

void setup() {
    pinMode(MOTOR_1_PIN, OUTPUT);
    pinMode(MOTOR_2_PIN, OUTPUT);

    // Initialize with 0 duty cycle, but set our desired frequency
    analogWrite(MOTOR_1_PIN, 0, PWM_FREQ);
    analogWrite(MOTOR_2_PIN, 0, PWM_FREQ);
}

void loop() {
    // Ramp up MOTOR 1
    for(int i = 0; i <= 255; i+=5) {
        analogWrite(MOTOR_1_PIN, i);
        delay(20);
    }
    analogWrite(MOTOR_1_PIN, 0); // Stop
    delay(500);

    // Ramp up MOTOR 2
    for(int i = 0; i <= 255; i+=5) {
        analogWrite(MOTOR_2_PIN, i);
        delay(20);
    }
    analogWrite(MOTOR_2_PIN, 0); // Stop
    delay(1000);
}
