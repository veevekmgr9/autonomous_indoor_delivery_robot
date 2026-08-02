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
float WHEEL_BASE = 0.125;          // meters
float MAX_LINEAR_SPEED = 0.25;    // m/s

// ================= ENCODERS =================

#define LEFT_ENCODER A0
#define RIGHT_ENCODER 13

volatile long leftTicks = 0;
volatile long rightTicks = 0;

volatile byte lastPortB;
volatile byte lastPortC;

// Encoder direction is inferred from motor command.
// This is required because these encoders provide only one signal.
volatile int leftEncoderDirection = 0;
volatile int rightEncoderDirection = 0;

unsigned long lastEncoderTime = 0;
const unsigned long ENCODER_INTERVAL = 50;   // 20 Hz



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



    // ---------------- ENCODERS ----------------

    pinMode(LEFT_ENCODER, INPUT_PULLUP);
    pinMode(RIGHT_ENCODER, INPUT_PULLUP);

    lastPortB = PINB;
    lastPortC = PINC;

    // Enable pin-change interrupts
    PCICR |= (1 << PCIE0);    // PORT B
    PCICR |= (1 << PCIE1);    // PORT C

    // D13 = PB5
    PCMSK0 |= (1 << PCINT5);

    // A0 = PC0
    PCMSK1 |= (1 << PCINT8);

    leftTicks = 0;
    rightTicks = 0;
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

    // ENCODER STREAM

    if (
        rosConnected &&
        millis() - lastEncoderTime >= ENCODER_INTERVAL
    )
    {
        lastEncoderTime = millis();
        sendEncoders();
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

    if (leftSpeed > 0.001)
        leftEncoderDirection = 1;
    else if (leftSpeed < -0.001)
        leftEncoderDirection = -1;
    else
        leftEncoderDirection = 0;


    if (rightSpeed > 0.001)
        rightEncoderDirection = 1;
    else if (rightSpeed < -0.001)
        rightEncoderDirection = -1;
    else
        rightEncoderDirection = 0;



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

// =====================================================
// ENCODER INTERRUPTS
// =====================================================

// RIGHT encoder D13 = PB5
ISR(PCINT0_vect)
{
    byte currentPortB = PINB;

    // Falling edge
    if ((lastPortB & _BV(PB5)) &&
        !(currentPortB & _BV(PB5)))
    {
        rightTicks += rightEncoderDirection;
    }

    lastPortB = currentPortB;
}


// LEFT encoder A0 = PC0
ISR(PCINT1_vect)
{
    byte currentPortC = PINC;

    // Falling edge
    if ((lastPortC & _BV(PC0)) &&
        !(currentPortC & _BV(PC0)))
    {
        leftTicks += leftEncoderDirection;
    }

    lastPortC = currentPortC;
}

// =====================================================
// ENCODER STREAM
// =====================================================

void sendEncoders()
{
    long L;
    long R;

    noInterrupts();

    L = leftTicks;
    R = rightTicks;

    interrupts();

    Serial.print("$ENC,");
    Serial.print(L);
    Serial.print(",");
    Serial.print(R);
    Serial.println("*");
}
