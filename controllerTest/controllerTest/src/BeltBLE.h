#pragma once
#include "Particle.h"

class BeltBLE
{
public:
    BeltBLE();
    ~BeltBLE();

    void setup(BleOnDataReceivedCallback callback, void* context);

    void transmit_orientation(float e1, float e2, float e3, float e4);

private:
    const BleUuid ServiceUuid{"62c3cf89-247b-4c0f-a70d-651080844609"};
    const BleUuid RxUuid{"62c3cf89-247b-4c0f-a70d-651080844609"};
    const BleUuid TxUuid{"62c3cf89-247b-4c0f-a70d-651080844608"};

    BleCharacteristic TxCharacteristic{"Tx", 
                                        BleCharacteristicProperty::NOTIFY, 
                                        TxUuid, 
                                        ServiceUuid};
    BleCharacteristic RxCharacteristic{"Rx", 
                                        BleCharacteristicProperty::WRITE_WO_RSP, 
                                        RxUuid,
                                        ServiceUuid};
};