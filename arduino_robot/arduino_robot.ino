#include <Wire.h>

const int MPU_addr = 0x68;


// ================= MOTOR PINS =================

#define PWMA 5
#define PWMB 6

#define AIN1 7
#define AIN2 11

#define BIN1 8
#define BIN2 10

#define STBY 3



// ================= MOTOR CONTROL =================

// Maximum PWM output
#define MAX_PWM 220


// Robot parameters
float WHEEL_BASE = 0.25;          // meters
float MAX_LINEAR_SPEED = 0.25;    // m/s



// ================= IMU DATA =================

int16_t ax, ay, az;
int16_t gx, gy, gz;


unsigned long lastImuTime = 0;

const unsigned long IMU_INTERVAL = 20; 
// 50Hz



// ================= SERIAL =================

String inputBuffer = "";

bool rosConnected = false;



// =====================================================
// I2C BUS RECOVERY
// =====================================================

void i2cBusRecovery()
{

    pinMode(A5, INPUT); 
    pinMode(A4, INPUT);


    if (digitalRead(A4) == LOW)
    {

        pinMode(A5, OUTPUT);


        for(int i=0;i<9;i++)
        {

            digitalWrite(A5,HIGH);
            delayMicroseconds(5);

            digitalWrite(A5,LOW);
            delayMicroseconds(5);

        }


        pinMode(A5,INPUT);

    }

}



// =====================================================
// SETUP
// =====================================================


void setup()
{

    Serial.begin(115200);



    i2cBusRecovery();


    Wire.begin();

    Wire.setWireTimeout(
        3000,
        true
    );



    // MPU6050 wake up

    Wire.beginTransmission(MPU_addr);

    Wire.write(0x6B);

    Wire.write(0);

    Wire.endTransmission(true);





    // Motor pins

    pinMode(PWMA,OUTPUT);
    pinMode(PWMB,OUTPUT);


    pinMode(AIN1,OUTPUT);
    pinMode(AIN2,OUTPUT);


    pinMode(BIN1,OUTPUT);
    pinMode(BIN2,OUTPUT);


    pinMode(STBY,OUTPUT);



    digitalWrite(STBY,HIGH);



    stopRobot();



    rosConnected=false;



    Serial.println("READY");

}





// =====================================================
// LOOP
// =====================================================


void loop()
{


    while(Serial.available()>0)
    {

        char c=(char)Serial.read();


        if(c=='\n' || c=='\r')
        {

            inputBuffer.trim();


            if(inputBuffer.length()>0)
            {
                processCommand(inputBuffer);
            }


            inputBuffer="";

        }
        else
        {

            inputBuffer += c;

        }

    }




    // IMU STREAM

    if(
        rosConnected &&
        millis()-lastImuTime >= IMU_INTERVAL
    )
    {

        lastImuTime=millis();

        sendIMU();

    }


}






// =====================================================
// COMMAND PROCESSOR
// =====================================================


void processCommand(String cmd)
{


    // ROS connection

    if(cmd=="START")
    {


        resetMPU();


        rosConnected=true;


        Serial.println(
            "MPU_RESET_COMPLETE"
        );


        return;

    }





    // Velocity command
    //
    // Format:
    //
    // V,linear,angular
    //
    // Example:
    //
    // V,0.08,0.0


    if(cmd.startsWith("V"))
    {


        int comma1 =
        cmd.indexOf(',');


        int comma2 =
        cmd.indexOf(
            ',',
            comma1+1
        );



        float linear =
        cmd.substring(
            comma1+1,
            comma2
        ).toFloat();



        float angular =
        cmd.substring(
            comma2+1
        ).toFloat();



        driveRobot(
            linear,
            angular
        );



        return;

    }




    if(cmd=="STOP")
    {

        stopRobot();

    }


}






// =====================================================
// MPU RESET
// =====================================================


void resetMPU()
{


    Wire.beginTransmission(MPU_addr);

    Wire.write(0x6B);

    Wire.write(0x80);

    Wire.endTransmission(true);



    delay(100);




    Wire.beginTransmission(MPU_addr);

    Wire.write(0x68);

    Wire.write(0x07);

    Wire.endTransmission(true);



    delay(100);





    Wire.beginTransmission(MPU_addr);

    Wire.write(0x6B);

    Wire.write(0x00);

    Wire.endTransmission(true);


}








// =====================================================
// IMU STREAM
// =====================================================


void sendIMU()
{


    Wire.beginTransmission(MPU_addr);


    Wire.write(0x3B);



    if(Wire.endTransmission(false)!=0)
        return;



    Wire.requestFrom(
        MPU_addr,
        14,
        true
    );



    if(Wire.available()>=14)
    {


        ax =
        Wire.read()<<8 |
        Wire.read();



        ay =
        Wire.read()<<8 |
        Wire.read();



        az =
        Wire.read()<<8 |
        Wire.read();



        // temperature skip

        Wire.read();
        Wire.read();



        gx =
        Wire.read()<<8 |
        Wire.read();



        gy =
        Wire.read()<<8 |
        Wire.read();



        gz =
        Wire.read()<<8 |
        Wire.read();




        Serial.print("$IMU,");


        Serial.print(ax);
        Serial.print(",");


        Serial.print(ay);
        Serial.print(",");


        Serial.print(az);
        Serial.print(",");


        Serial.print(gx);
        Serial.print(",");


        Serial.print(gy);
        Serial.print(",");


        Serial.print(gz);


        Serial.println("*");

    }


}








// =====================================================
// DIFFERENTIAL DRIVE
// =====================================================


void driveRobot(
float linear,
float angular
)
{


    float leftSpeed =
    linear -
    (angular * WHEEL_BASE / 2.0);



    float rightSpeed =
    linear +
    (angular * WHEEL_BASE / 2.0);





    int leftPWM =
    abs(
        leftSpeed /
        MAX_LINEAR_SPEED *
        MAX_PWM
    );



    int rightPWM =
    abs(
        rightSpeed /
        MAX_LINEAR_SPEED *
        MAX_PWM
    );




    leftPWM =
    constrain(
        leftPWM,
        0,
        MAX_PWM
    );



    rightPWM =
    constrain(
        rightPWM,
        0,
        MAX_PWM
    );







    // LEFT MOTOR


    if(leftSpeed>0)
    {

        digitalWrite(AIN1,HIGH);

        digitalWrite(AIN2,LOW);

    }

    else if(leftSpeed<0)
    {

        digitalWrite(AIN1,LOW);

        digitalWrite(AIN2,HIGH);

    }

    else
    {

        digitalWrite(AIN1,LOW);

        digitalWrite(AIN2,LOW);

    }







    // RIGHT MOTOR


    if(rightSpeed>0)
    {

        digitalWrite(BIN1,HIGH);

        digitalWrite(BIN2,LOW);

    }

    else if(rightSpeed<0)
    {

        digitalWrite(BIN1,LOW);

        digitalWrite(BIN2,HIGH);

    }

    else
    {

        digitalWrite(BIN1,LOW);

        digitalWrite(BIN2,LOW);

    }




// Minimum starting torque
    if(leftPWM > 0 && leftPWM < 100)
    {
        leftPWM = 100;
    }
    
    
    if(rightPWM > 0 && rightPWM < 100)
    {
        rightPWM = 100;
    }
    
    
    analogWrite(PWMA,leftPWM);
    analogWrite(PWMB,rightPWM);



}









// =====================================================
// STOP
// =====================================================


void stopRobot()
{


    analogWrite(PWMA,0);

    analogWrite(PWMB,0);



    digitalWrite(AIN1,LOW);

    digitalWrite(AIN2,LOW);



    digitalWrite(BIN1,LOW);

    digitalWrite(BIN2,LOW);


}
