#include "BeltIMU.h"

BeltIMU::BeltIMU() :
    bno08x(-1),
    oldQuat{1,0,0,0}
{
    return;
}

BeltIMU::~BeltIMU(){}

void BeltIMU::setup(Quat initialOrientation){
    if (!bno08x.begin_I2C()) {
        //if (!bno08x.begin_UART(&Serial1)) {  // Requires a device with > 300 byte UART buffer!
        //if (!bno08x.begin_SPI(BNO08X_CS, BNO08X_INT)) {
        Serial.println("Failed to find BNO08x chip");
        
    }

    set_reports();
    initQ = Qnormalize(initialOrientation);
    Serial.println("Reading IMU events");
}

bool BeltIMU::check_connection() {
    if (bno08x.wasReset()) {
        Serial.print("IMU was reset, attempting to set reports ");
        bool reEnabled = set_reports();
        return reEnabled;
    }
    return true;
}

Quat BeltIMU::get_quaternion () {
    sh2_SensorValue_t data;
    if (!bno08x.getSensorEvent(&data)) {
        Serial.println("could not retrieve IMU event");
        return oldQuat;
    }
    float qw = data.un.rotationVector.real;
    float qx = data.un.rotationVector.i;
    float qy = data.un.rotationVector.j;
    float qz = data.un.rotationVector.k;
    Quat newQuat{qw,qx,qy,qz};

    // rotate quaternion by opposite of initial orientation quaternion
    // to find quaternion relative to initial orientation
    Quat reorientedQuat = Qmultiply( newQuat, Qconj(initQ) );
    
    oldQuat = reorientedQuat;

    return reorientedQuat;
}


/****************
 Private
*****************/
bool BeltIMU::set_reports() {
    Serial.println("Setting desired reports");
    if (! bno08x.enableReport(SH2_GAME_ROTATION_VECTOR)) {
        Serial.println("Could not enable game vector");
        return false;
    }
    return true;
}

/****************
 Quaternion Stuff
*****************/
Quat Qmultiply(const Quat& a, const Quat& b) {
    float qw = a.w*b.w - a.x*b.x - a.y*b.y - a.z*b.z;
    float qx = a.w*b.x + a.x*b.w + a.y*b.z - a.z*b.y;
    float qy = a.w*b.y - a.x*b.z + a.y*b.w + a.z*b.x;
    float qz = a.w*b.z + a.x*b.y - a.y*b.x + a.z*b.w;
    
    Quat qnew{qw, qx, qy, qz};
    return Qnormalize(qnew);
}

Quat Qconj(const Quat& q) {
    return {q.w, -q.x, -q.y, -q.z};
}

Quat Qnormalize(Quat q) {
    float n = sqrt(q.w*q.w + q.x*q.x + q.y*q.y + q.z*q.z);
    return {q.w/n, q.x/n, q.y/n, q.z/n};
}

void printQuat(Quat q) {
    Serial.print("qw:");
    Serial.print(q.w);
    Serial.print(" qx:");
    Serial.print(q.x);
    Serial.print(" qy:");
    Serial.print(q.y);
    Serial.print(" qz:");
    Serial.print(q.z);
    Serial.println("");
}