#pragma once
#include  "Adafruit_BNO08x_Sahagun.h"

// implementation at end of cpp file
struct Quat {
    float w, x, y, z;
};
Quat Qmultiply(const Quat& a, const Quat& b);
Quat Qconj(const Quat& q);
Quat Qnormalize(Quat q);
void printQuat(Quat q);


class BeltIMU
{
public:
    BeltIMU();
    ~BeltIMU();

    void setup(Quat initialOrientation = {1,0,0,0});

    bool check_connection();

    Quat get_quaternion ();
    
private:
    Adafruit_BNO08x bno08x;
    Quat oldQuat;
    Quat initQ;

    bool setReports();

};



