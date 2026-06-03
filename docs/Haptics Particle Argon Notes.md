# BLE stuff
look at ppcp for improving transfer rates

Making services:
```cpp
// PROTOTYPE 
BleUuid(const String& uuid); 
BleUuid(const char* uuid);
// EXAMPLE 
BleUuid myCustomService("240d5183-819a-4627-9ca9-1aa24df29f18");
```


Giving Services characteristics
- no separate class for the characteristic, a characteristic is determined buy a uuid as well
```cpp
// global variables
BleUuid myCustomCharacteristicUuid("240d5183-819a-4627-9ca9-1aa24df29f18");


//example implementation
BleCharacteristic customChar("temp",
 							BleCharacteristicProperty::NOTIFY, //see below
 							myCustomCharacteristicUuid, 
 							myCustomService);

// then I think you need to add the characteristic
// in setup
setup() {
	BLE.addCharacteristic(customChar);
}
```


Appending services to the advertisement:
```cpp
// in setup:
BleAdvertisingData advData;
advData.appendServiceUUID(myCustomService);

BLE.setDeviceName("Argon Test");
BLE.advertise();
```

Different Characteristic Properties:
> [!info]+ BLE Characteristic Properties:
> - `BleCharacteristicProperty::BROADCAST` (0x01) The value can be broadcast.
>- `BleCharacteristicProperty::READ` (0x02) The value can be read.
> - `BleCharacteristicProperty::WRITE_WO_RSP` (0x04) The value can be written without acknowledgement. For example, the UART peripheral example uses this characteristic properly to receive UART data from the central device.
> - `BleCharacteristicProperty::WRITE` (0x08) The value can be written to the peripheral from the central device.
> - `BleCharacteristicProperty::NOTIFY` (0x10) The value is published by the peripheral without acknowledgement. This is the standard way peripherals periodically publish data.
> - `BleCharacteristicProperty::INDICATE` (0x20) The value can be indicated, basically publish with acknowledgement.
> - `BleCharacteristicProperty::AUTH_SIGN_WRITES` (0x40) The value supports signed writes. This is operation not supported.
> - `BleCharacteristicProperty::EXTENDED_PROP` (0x80) The value supports extended properties. This operation is not supported.


characteristics can have one or more values



How to actually do stuff with characteristics:
BLE characteristic w/ data recieved:


```cpp
// Global variable 
BleCharacteristic(	const char* desc, 
					BleCharacteristicProperty properties, 
					BleUuid charUuid, 
					BleUuid svcUuid, 
					BleOnDataReceivedCallback callback = nullptr, 
					void* context = nullptr) // context is extra info sent to 
											// callback (typically "this" if an 
											// object)

BleCharacteristic rxCharacteristic("rx",
 								  	BleCharacteristicProperty::WRITE_WO_RSP,
 								  	rxUuid, 
 								  	serviceUuid, 
 								  	onDataReceived, 
 								  	NULL);
 								  	
// The onDataRecieved is a callback function:
void onDataReceived(const uint8_t* data, 
					size_t len, 
					const BlePeerDevice& peer, 
					void* context)


// in setup, need to register characteristic (if a peripheral)
setup() {
	BLE.addCharacteristic(customChar);
	
	// can also tie the callback here
	myCharacteristic.onDataReceived(onDataReceived, NULL);
}
```

The `onDataReceived()` handler is run from the BLE thread. You should avoid lengthy or blocking operations since it will affect other BLE processing. Additionally, the BLE thread has a smaller stack than the main application (loop) thread, so you avoid functions that require a large amount of stack space. To prevent these issues, you should set a flag in the data received handler and perform lengthy or stack-intensive operations from the `loop()` instead. For example, you should not call `Particle.publish()`, `WiFi.clearCredentials()`, and many other functions directly from the onDataReceived handler.

To write data to a characteristic:
```cpp
// PROTOTYPE template
<typename T> 
ssize_t setValue(T val) const; 
// EXAMPLE 
uint16_t value = 0x1234; 
characteristic.setValue(value);
```
this apparently works with arbitrary data types including structs somehow I will have to test how that works



Because the onDataReceived is run on another thread, might have to do thread safety stuff
Log.info() is thread safe, serial is not

need to use a recursive mutex if one thread will be locking 

mutex example
```cpp
// globally
Mutex coordsMutex;

// in a funciton
WITH_LOCK(coordsMutex) {  
	localX = x;  
	localY = y;  
	localZ = z;  
}
```




## useful data transmission functions:
sscanf "string scan formatted"
parses formatted data from c string
<span style="color:rgb(192, 0, 0)">note c strings must end in a 0 byte</span> `'\0'`

address operator:
sscanf needs pointers to variables so it can write results.  
  
Correct:  
&x  
  
Incorrect:  
x
```cpp
int sscanf(const char* str, const char* format, ...); //returns number of successfully matched values 

char text[] = "1.23,4.56,7.89";

float x,y,z;
int matched = sscanf(  
	text,  
	"%f,%f,%f",  
	&x,  
	&y,  
	&z  
);
```

note:
uint8_t is exactly 1 byte of memory (8 bits per byte)
note the data arg for callback is: `const uint8_t* data`
- stores an array of bytes essentially

```cpp
void onDataReceived(const uint8_t* data, 
					size_t len, 
					const BlePeerDevice& peer, 
					void* context)
{
	// buffer to hold text  
	char buffer[64];  
	  
	// avoid overflowing the buffer  
	size_t copyLen = min(len, sizeof(buffer) - 1);  
	  
	// copy raw BLE bytes into char buffer  
	memcpy(buffer, data, copyLen);  
	  
	// add null terminator  
	buffer[copyLen] = '\0';  
	  
	// now buffer is a valid C string
}

```


the context actually must be casted into the correct pointer type for the class context you want:
```cpp
void onDataReceived(const uint8_t* data, 
					size_t len, 
					const BlePeerDevice& peer, 
					void* context)
{
MyClass* self = (MyClass*)context;
}
```



here is some function passing sematic stuff:
```cpp
class MainClass 
{
private:   
	 BleHandler ble;    
	 CallbackClass callbackClass;
 public:    
	 void setup() {        
	 	ble.setup(CallbackClass::onCallback, &callbackClass);    
	 }
 };
```

```cpp
class BleHandler {  
private:  
	BleCharacteristic rx;  
  
public:  
	void setup(BleOnDataReceivedCallback callback, void* context) {  
		rx.onDataReceived(callback, context);  
	}  
};
```

```cpp
class CallbackClass {  
public:  
	static void onCallback(const uint8_t* data,  
						   size_t len,  
						   const BlePeerDevice& peer,  
						   void* context)  
	{  
		CallbackClass* self = static_cast<CallbackClass*>(context);  
		self->handleData(data, len, peer);  
	}  

private:  
	void handleData(const uint8_t* data,  
					size_t len,  
					const BlePeerDevice& peer)  
	{  
	// can access private members here  
	}
};
```