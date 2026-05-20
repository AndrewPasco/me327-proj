#include "BeltBLE.h"

BeltBLE::BeltBLE() {
    
}

BeltBLE::~BeltBLE() {
    
}

void BeltBLE::transmit_orientation(float e1, float e2, float e3, float e4) {
    String toTransmit = String::format("%.2f,%.2f,%.2f,%.2f", e1, e2, e3, e4);
    Serial.println("transmitting:");
    Serial.println(toTransmit);
    TxCharacteristic.setValue(toTransmit);
}

void BeltBLE::setup(BleOnDataReceivedCallback callback, void* context) {
    // pass callback to Rx
    RxCharacteristic.onDataReceived(callback, context);

    // register characteristics
    BLE.addCharacteristic(TxCharacteristic);
    BLE.addCharacteristic(RxCharacteristic);

    // make sure to advertise the custom service
    BleAdvertisingData advData;
    advData.appendServiceUUID(ServiceUuid); 

    // set the advertising name
    BLE.setDeviceName("Argon Test");

    BLE.advertise();
}