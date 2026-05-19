/* 
 * Project myProject
 * Author: Your Name
 * Date: 
 * For comprehensive documentation and examples, please visit:
 * https://docs.particle.io/firmware/best-practices/firmware-template/
 */

// Include Particle Device OS APIs
#include "Particle.h"
// #include  "Adafruit_BNO08x_Sahagun.h"

int light = D7;
// Let Device OS manage the connection to the Particle Cloud
SYSTEM_MODE(AUTOMATIC);

// Run the application and system concurrently in separate threads
SYSTEM_THREAD(ENABLED);

// Show system, cloud connectivity, and application logs over USB
// View logs with CLI using 'particle serial monitor --follow'
SerialLogHandler logHandler(LOG_LEVEL_INFO);

String byteString = "hello"; // will be overriding this string in receiving funciton

Mutex coordsMutex; // Mutex are used to ensure two threads do not access the same data at the same time
                   // The BLE docs for the argon say that ble callbacks run in a separate thread so this
                   // is probably necessary to avoid race conditions

void onDataReceived(const uint8_t* data, 
					size_t len, 
					const BlePeerDevice& peer, 
					void* context); // Callback function for when Rx service has new data

// Services and their characteristics require UUIDs
// I think in most places just a plain string also works here
BleUuid coordServiceUuid("62c3cf89-247b-4c0f-a70d-651080844609");
BleUuid RxUuid("62c3cf89-247b-4c0f-a70d-651080844609");
BleUuid coordTxUuid("62c3cf89-247b-4c0f-a70d-651080844608");

// instantiate the characteristics (places to send and recieve data to). They are global here as they
// need to be accessed 
BleCharacteristic coordCharacteristic("Orientation", BleCharacteristicProperty::NOTIFY, coordTxUuid, coordServiceUuid);
BleCharacteristic inputChar("Rx", BleCharacteristicProperty::WRITE_WO_RSP, RxUuid, coordServiceUuid,onDataReceived);

// setup() runs once, when the device is first turned on
void setup() {
  Serial.begin(9600);
  delay(10000);
  waitFor(Serial.isConnected, 10000);

  uint8_t mac[6];
  WiFi.macAddress(mac);
  
  // Print the MAC address
  Serial.printlnf("Wi-Fi MAC Address: %02x:%02x:%02x:%02x:%02x:%02x", 
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

  // add the transmit and recieve characteristics to nble
  BLE.addCharacteristic(coordCharacteristic);
  BLE.addCharacteristic(inputChar);

  // make sure to advertise the custom service
  BleAdvertisingData advData;
  advData.appendServiceUUID(coordServiceUuid); 

  // set the advertising name
  BLE.setDeviceName("Argon Test");

  BLE.advertise();

  // light pin
  pinMode(light,OUTPUT);
}

// loop() runs over and over again, as quickly as it can execute.
void loop() {
  // blink the thing
  digitalWrite(light,HIGH);
  delay(1000);
  digitalWrite(light,LOW);
  delay(1000);

  // lock thread when accessing the byte string to avoid race condition
  WITH_LOCK(coordsMutex) {
    Serial.println(byteString);
  }

  // place numbers in a formatted string

  static int i = 0;
  int mynums[3] = {i,2,3};
  String toTransmit = String::format("%.2f,%.2f,%.2f", mynums[0],mynums[1],mynums[2]);
  coordCharacteristic.setValue(toTransmit);
  i++;
}

void onDataReceived(const uint8_t* data, 
					size_t len, 
					const BlePeerDevice& peer, 
					void* context)
{
  char buffer[64];
  // avoid overflowing the buffer  
	size_t copyLen = min(len, sizeof(buffer) - 1);
	// copy raw BLE bytes into char buffer  
	memcpy(buffer, data, copyLen); 

  buffer[copyLen] = '\0';

  WITH_LOCK(coordsMutex) {
    byteString = buffer;
  }
}