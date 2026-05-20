/* 
 * Project myProject
 * Author: Your Name
 * Date: 
 * For comprehensive documentation and examples, please visit:
 * https://docs.particle.io/firmware/best-practices/firmware-template/
 */

// Include Particle Device OS APIs
#include "Particle.h"
#include "HapticBelt.h"
#include  "Adafruit_BNO08x_Sahagun.h"

int light = D7;
// Let Device OS manage the connection to the Particle Cloud
SYSTEM_MODE(AUTOMATIC);

// Run the application and system concurrently in separate threads
SYSTEM_THREAD(ENABLED);


// Show system, cloud connectivity, and application logs over USB
// View logs with CLI using 'particle serial monitor --follow'
SerialLogHandler logHandler(LOG_LEVEL_INFO);


HapticBelt Belt;

void setup()
{
  Serial.begin(9600);
  delay(5000);
  waitFor(Serial.isConnected, 5000);
  Belt.setup();

  BleAddress addr = BLE.address();
  Serial.printlnf("BLE MAC: %s", addr.toString().c_str());
}

void loop()
{
  Belt.loop();
}


// String byteString = "hello"; // will be overriding this string in receiving funciton

// Mutex coordsMutex; // Mutex are used to ensure two threads do not access the same data at the same time
//                    // The BLE docs for the argon say that ble callbacks run in a separate thread so this
//                    // is probably necessary to avoid race conditions

// void rxcallback(const uint8_t* data, 
// 					size_t len, 
// 					const BlePeerDevice& peer, 
// 					void* context); // Callback function for when Rx service has new data

// // Services and their characteristics require UUIDs
// // I think in most places just a plain string also works here
// const BleUuid ServiceUuid{"62c3cf89-247b-4c0f-a70d-651080844609"};
// const BleUuid RxUuid{"62c3cf89-247b-4c0f-a70d-651080844609"};
// const BleUuid TxUuid{"62c3cf89-247b-4c0f-a70d-651080844608"};

// BleCharacteristic TxCharacteristic{"Tx", 
//                                     BleCharacteristicProperty::NOTIFY, 
//                                     TxUuid, 
//                                     ServiceUuid};
// BleCharacteristic RxCharacteristic{"Rx", 
//                                     BleCharacteristicProperty::WRITE_WO_RSP, 
//                                     RxUuid,
//                                     ServiceUuid};

// // instantiate the characteristics (places to send and recieve data to). They are global here as they
// // need to be accessed 

// // setup() runs once, when the device is first turned on
// void setup() {
//   Serial.begin(9600);
//   delay(5000);
//   waitFor(Serial.isConnected, 5000);

//   uint8_t mac[6];
//   WiFi.macAddress(mac);
  
//   // Print the MAC address
//   Serial.printlnf("Wi-Fi MAC Address: %02x:%02x:%02x:%02x:%02x:%02x", 
//            mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);


//   // add callback to characteristic
//   RxCharacteristic.onDataReceived(rxcallback, NULL);

//   // add the transmit and recieve characteristics to ble

//   BLE.addCharacteristic(TxCharacteristic);
//   BLE.addCharacteristic(RxCharacteristic);

//   // make sure to advertise the custom service
//   BleAdvertisingData advData;
//   advData.appendServiceUUID(ServiceUuid); 

//   // set the advertising name
//   BLE.setDeviceName("Argon Test");

//   BLE.advertise();

//   // light pin
//   pinMode(light,OUTPUT);
// }

// // loop() runs over and over again, as quickly as it can execute.
// void loop() {
//   // blink the thing
//   digitalWrite(light,HIGH);
//   delay(1000);
//   digitalWrite(light,LOW);
//   delay(1000);

//   // lock thread when accessing the byte string to avoid race condition
//   WITH_LOCK(coordsMutex) {
//     Serial.println(byteString);
//   }

//   // place numbers in a formatted string

//   static int i = 0;
//   int mynums[3] = {i,2,3};
//   String toTransmit = String::format("%.2f,%.2f,%.2f", mynums[0],mynums[1],mynums[2]);
//   TxCharacteristic.setValue(toTransmit);
//   i++;
// }

// void rxcallback(const uint8_t* data, 
// 					size_t len, 
// 					const BlePeerDevice& peer, 
// 					void* context)
// {
//   char buffer[64];
//   // avoid overflowing the buffer  
// 	size_t copyLen = min(len, sizeof(buffer) - 1);
// 	// copy raw BLE bytes into char buffer  
// 	memcpy(buffer, data, copyLen); 

//   buffer[copyLen] = '\0';

//   WITH_LOCK(coordsMutex) {
//     byteString = buffer;
//   }
// }