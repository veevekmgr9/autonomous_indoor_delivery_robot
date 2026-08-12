#include <Wire.h>

const int MPU_addr = 0x68;


// =====================================================
// MOTOR PINS
// =====================================================

#define PWMA 5
#define PWMB 6

#define AIN1 7
#define AIN2 11

#define BIN1 8
#define BIN2 10

#define STBY 3


// =====================================================
// MOTOR CONTROL
// =====================================================

#define MAX_PWM 140

float WHEEL_BASE = 0.125;          // metres
float MAX_LINEAR_SPEED = 0.20;     // m/s


// =====================================================
// ENCODERS
// =====================================================
//
// ACTUAL HARDWARE:
//
// Left encoder  signal -> A1
// Right encoder signal -> A2
//
// Arduino UNO:
//
// A1 = PC1 = PCINT9
// A2 = PC2 = PCINT10
//
// Both encoders are on PORT C.
// =====================================================

#define LEFT_ENCODER  A1
#define RIGHT_ENCODER A2

volatile long leftTicks = 0;
volatile long rightTicks = 0;


// Direction is inferred from motor command.
//
// +1 = forward
// -1 = reverse
//  0 = stopped
//
volatile int leftEncoderDirection = 0;
volatile int rightEncoderDirection = 0;


// Previous PORT C state
volatile byte lastPortC;


// Encoder stream rate
unsigned long lastEncoderTime = 0;

const unsigned long ENCODER_INTERVAL = 50;
// 20 Hz


// =====================================================
// ULTRASONIC SENSOR
// =====================================================
//
// ELEGOO SmartCar Shield V1.1
//
// TRIG = D13
// ECHO = D12
// =====================================================

#define ULTRASONIC_TRIG 13
#define ULTRASONIC_ECHO 12


// Ultrasonic measurement interval
unsigned long lastUltrasonicTrigger = 0;

const unsigned long ULTRASONIC_INTERVAL = 100;
// 10 Hz


// -----------------------------------------------------
// Non-blocking ultrasonic state machine
// -----------------------------------------------------

enum UltrasonicState
{
    ULTRA_IDLE,
    ULTRA_WAIT_RISE,
    ULTRA_WAIT_FALL
};

UltrasonicState ultrasonicState = ULTRA_IDLE;


// Time echo went HIGH
unsigned long ultrasonicEchoStart = 0;


// Last valid distance
float ultrasonicDistance = -1.0;


// Timeout for echo
const unsigned long ULTRASONIC_TIMEOUT = 25000;
// 25 ms ≈ 4.3 metres maximum


// =====================================================
// IMU
// =====================================================

int16_t ax, ay, az;
int16_t gx, gy, gz;

unsigned long lastImuTime = 0;

const unsigned long IMU_INTERVAL = 20;
// 50 Hz


// =====================================================
// SERIAL
// =====================================================

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


        for (int i = 0; i < 9; i++)
        {
            digitalWrite(A5, HIGH);
            delayMicroseconds(5);

            digitalWrite(A5, LOW);
            delayMicroseconds(5);
        }


        pinMode(A5, INPUT);
    }
}


// =====================================================
// SETUP
// =====================================================

void setup()
{
    Serial.begin(115200);


    // =================================================
    // I2C
    // =================================================

    i2cBusRecovery();

    Wire.begin();

    Wire.setWireTimeout(
        3000,
        true
    );


    // =================================================
    // MPU6050 WAKE UP
    // =================================================

    Wire.beginTransmission(MPU_addr);

    Wire.write(0x6B);
    Wire.write(0x00);

    Wire.endTransmission(true);


    // =================================================
    // MOTOR PINS
    // =================================================

    pinMode(PWMA, OUTPUT);
    pinMode(PWMB, OUTPUT);

    pinMode(AIN1, OUTPUT);
    pinMode(AIN2, OUTPUT);

    pinMode(BIN1, OUTPUT);
    pinMode(BIN2, OUTPUT);

    pinMode(STBY, OUTPUT);

    digitalWrite(STBY, HIGH);

    stopRobot();


    // =================================================
    // ENCODERS
    // =================================================

    pinMode(
        LEFT_ENCODER,
        INPUT_PULLUP
    );

    pinMode(
        RIGHT_ENCODER,
        INPUT_PULLUP
    );


    // Read initial PORT C state

    lastPortC = PINC;


    // Enable PORT C pin-change interrupt

    PCICR |= (1 << PCIE1);


    // A1 = PC1 = PCINT9

    PCMSK1 |= (1 << PCINT9);


    // A2 = PC2 = PCINT10

    PCMSK1 |= (1 << PCINT10);


    leftTicks = 0;
    rightTicks = 0;


    // =================================================
    // ULTRASONIC
    // =================================================

    pinMode(
        ULTRASONIC_TRIG,
        OUTPUT
    );

    pinMode(
        ULTRASONIC_ECHO,
        INPUT
    );


    digitalWrite(
        ULTRASONIC_TRIG,
        LOW
    );


    ultrasonicState = ULTRA_IDLE;

    ultrasonicDistance = -1.0;


    // =================================================
    // CONNECTION
    // =================================================

    rosConnected = false;


    Serial.println("READY");
}


// =====================================================
// MAIN LOOP
// =====================================================

void loop()
{
    // =================================================
    // SERIAL COMMAND PROCESSING
    // =================================================

    while (Serial.available() > 0)
    {
        char c = (char)Serial.read();


        if (
            c == '\n' ||
            c == '\r'
        )
        {
            inputBuffer.trim();


            if (inputBuffer.length() > 0)
            {
                processCommand(inputBuffer);
            }


            inputBuffer = "";
        }
        else
        {
            inputBuffer += c;
        }
    }


    // =================================================
    // IMU
    // =================================================

    if (
        rosConnected &&
        millis() - lastImuTime >= IMU_INTERVAL
    )
    {
        lastImuTime = millis();

        sendIMU();
    }


    // =================================================
    // ENCODERS
    // =================================================

    if (
        rosConnected &&
        millis() - lastEncoderTime >= ENCODER_INTERVAL
    )
    {
        lastEncoderTime = millis();

        sendEncoders();
    }


    // =================================================
    // ULTRASONIC
    // =================================================

    if (rosConnected)
    {
        updateUltrasonic();
    }
}


// =====================================================
// COMMAND PROCESSOR
// =====================================================

void processCommand(String cmd)
{
    // =================================================
    // START
    // =================================================

    if (cmd == "START")
    {
        resetMPU();

        rosConnected = true;


        // Reset encoder directions

        leftEncoderDirection = 0;
        rightEncoderDirection = 0;


        // Reset ultrasonic state

        ultrasonicState = ULTRA_IDLE;

        ultrasonicDistance = -1.0;


        lastUltrasonicTrigger = millis();


        Serial.println(
            "MPU_RESET_COMPLETE"
        );


        return;
    }


    // =================================================
    // VELOCITY COMMAND
    //
    // V,linear,angular
    //
    // Example:
    //
    // V,0.08,0.0
    // =================================================

    if (cmd.startsWith("V"))
    {
        int comma1 =
            cmd.indexOf(',');


        int comma2 =
            cmd.indexOf(
                ',',
                comma1 + 1
            );


        if (
            comma1 == -1 ||
            comma2 == -1
        )
        {
            return;
        }


        float linear =
            cmd.substring(
                comma1 + 1,
                comma2
            ).toFloat();


        float angular =
            cmd.substring(
                comma2 + 1
            ).toFloat();


        driveRobot(
            linear,
            angular
        );


        return;
    }


    // =================================================
    // STOP
    // =================================================

    if (cmd == "STOP")
    {
        stopRobot();
    }
}


// =====================================================
// MPU RESET
// =====================================================

void resetMPU()
{
    // -------------------------------------------------
    // Reset MPU
    // -------------------------------------------------

    Wire.beginTransmission(MPU_addr);

    Wire.write(0x6B);
    Wire.write(0x80);

    Wire.endTransmission(true);


    delay(100);


    // -------------------------------------------------
    // Reset signal paths
    // -------------------------------------------------

    Wire.beginTransmission(MPU_addr);

    Wire.write(0x68);
    Wire.write(0x07);

    Wire.endTransmission(true);


    delay(100);


    // -------------------------------------------------
    // Wake MPU
    // -------------------------------------------------

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


    if (
        Wire.endTransmission(false) != 0
    )
    {
        return;
    }


    Wire.requestFrom(
        MPU_addr,
        14,
        true
    );


    if (Wire.available() >= 14)
    {
        // ------------------------------------------------
        // ACCELEROMETER
        // ------------------------------------------------

        ax =
            Wire.read() << 8 |
            Wire.read();


        ay =
            Wire.read() << 8 |
            Wire.read();


        az =
            Wire.read() << 8 |
            Wire.read();


        // ------------------------------------------------
        // TEMPERATURE
        // ------------------------------------------------

        Wire.read();
        Wire.read();


        // ------------------------------------------------
        // GYROSCOPE
        // ------------------------------------------------

        gx =
            Wire.read() << 8 |
            Wire.read();


        gy =
            Wire.read() << 8 |
            Wire.read();


        gz =
            Wire.read() << 8 |
            Wire.read();


        // ------------------------------------------------
        // SERIAL OUTPUT
        // ------------------------------------------------

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
    // -------------------------------------------------
    // Turning sensitivity
    // -------------------------------------------------

    angular *= 0.4;


    // -------------------------------------------------
    // Calculate wheel speeds
    // -------------------------------------------------

    float leftSpeed =
        linear +
        (
            angular *
            WHEEL_BASE /
            2.0
        );


    float rightSpeed =
        linear -
        (
            angular *
            WHEEL_BASE /
            2.0
        );


    // -------------------------------------------------
    // LEFT ENCODER DIRECTION
    // -------------------------------------------------

    if (leftSpeed > 0.001)
    {
        leftEncoderDirection = 1;
    }
    else if (leftSpeed < -0.001)
    {
        leftEncoderDirection = -1;
    }
    else
    {
        leftEncoderDirection = 0;
    }


    // -------------------------------------------------
    // RIGHT ENCODER DIRECTION
    // -------------------------------------------------

    if (rightSpeed > 0.001)
    {
        rightEncoderDirection = 1;
    }
    else if (rightSpeed < -0.001)
    {
        rightEncoderDirection = -1;
    }
    else
    {
        rightEncoderDirection = 0;
    }


    // -------------------------------------------------
    // PWM CALCULATION
    // -------------------------------------------------

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


    // =================================================
    // LEFT MOTOR
    // =================================================

    if (leftSpeed > 0)
    {
        digitalWrite(
            AIN1,
            HIGH
        );

        digitalWrite(
            AIN2,
            LOW
        );
    }
    else if (leftSpeed < 0)
    {
        digitalWrite(
            AIN1,
            LOW
        );

        digitalWrite(
            AIN2,
            HIGH
        );
    }
    else
    {
        digitalWrite(
            AIN1,
            LOW
        );

        digitalWrite(
            AIN2,
            LOW
        );
    }


    // =================================================
    // RIGHT MOTOR
    // =================================================

    if (rightSpeed > 0)
    {
        digitalWrite(
            BIN1,
            HIGH
        );

        digitalWrite(
            BIN2,
            LOW
        );
    }
    else if (rightSpeed < 0)
    {
        digitalWrite(
            BIN1,
            LOW
        );

        digitalWrite(
            BIN2,
            HIGH
        );
    }
    else
    {
        digitalWrite(
            BIN1,
            LOW
        );

        digitalWrite(
            BIN2,
            LOW
        );
    }


    // =================================================
    // MINIMUM STARTING TORQUE
    // =================================================

    const int MIN_PWM = 80;


    if (
        leftPWM > 0 &&
        leftPWM < MIN_PWM
    )
    {
        leftPWM = MIN_PWM;
    }


    if (
        rightPWM > 0 &&
        rightPWM < MIN_PWM
    )
    {
        rightPWM = MIN_PWM;
    }


    // =================================================
    // APPLY PWM
    // =================================================

    analogWrite(
        PWMA,
        leftPWM
    );


    analogWrite(
        PWMB,
        rightPWM
    );
}


// =====================================================
// STOP ROBOT
// =====================================================

void stopRobot()
{
    analogWrite(
        PWMA,
        0
    );


    analogWrite(
        PWMB,
        0
    );


    digitalWrite(
        AIN1,
        LOW
    );

    digitalWrite(
        AIN2,
        LOW
    );


    digitalWrite(
        BIN1,
        LOW
    );

    digitalWrite(
        BIN2,
        LOW
    );


    // Robot stopped

    leftEncoderDirection = 0;
    rightEncoderDirection = 0;
}


// =====================================================
// ENCODER INTERRUPT
// =====================================================
//
// A1 = PC1 = LEFT
// A2 = PC2 = RIGHT
//
// Falling edge detection.
//
// Direction comes from the motor command.
// =====================================================

ISR(PCINT1_vect)
{
    byte currentPortC = PINC;


    // -------------------------------------------------
    // LEFT ENCODER
    // A1 / PC1
    // -------------------------------------------------

    if (
        (lastPortC & _BV(PC1)) &&
        !(currentPortC & _BV(PC1))
    )
    {
        leftTicks += leftEncoderDirection;
    }


    // -------------------------------------------------
    // RIGHT ENCODER
    // A2 / PC2
    // -------------------------------------------------

    if (
        (lastPortC & _BV(PC2)) &&
        !(currentPortC & _BV(PC2))
    )
    {
        rightTicks += rightEncoderDirection;
    }


    // Save current state

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


// =====================================================
// NON-BLOCKING ULTRASONIC
// =====================================================

void updateUltrasonic()
{
    unsigned long now = micros();


    // =================================================
    // IDLE
    // =================================================

    if (ultrasonicState == ULTRA_IDLE)
    {
        if (
            millis() -
            lastUltrasonicTrigger >=
            ULTRASONIC_INTERVAL
        )
        {
            lastUltrasonicTrigger = millis();


            // ------------------------------------------------
            // Trigger pulse
            // ------------------------------------------------

            digitalWrite(
                ULTRASONIC_TRIG,
                LOW
            );

            delayMicroseconds(2);


            digitalWrite(
                ULTRASONIC_TRIG,
                HIGH
            );

            delayMicroseconds(10);


            digitalWrite(
                ULTRASONIC_TRIG,
                LOW
            );


            // Start waiting for echo

            ultrasonicState =
                ULTRA_WAIT_RISE;

            ultrasonicEchoStart = now;
        }


        return;
    }


    // =================================================
    // WAIT FOR ECHO TO GO HIGH
    // =================================================

    if (
        ultrasonicState ==
        ULTRA_WAIT_RISE
    )
    {
        if (
            digitalRead(
                ULTRASONIC_ECHO
            ) == HIGH
        )
        {
            ultrasonicEchoStart =
                micros();

            ultrasonicState =
                ULTRA_WAIT_FALL;

            return;
        }


        // ------------------------------------------------
        // Timeout
        // ------------------------------------------------

        if (
            micros() -
            ultrasonicEchoStart >
            ULTRASONIC_TIMEOUT
        )
        {
            ultrasonicDistance = -1.0;

            ultrasonicState =
                ULTRA_IDLE;

            sendUltrasonic();

            return;
        }


        return;
    }


    // =================================================
    // WAIT FOR ECHO TO GO LOW
    // =================================================

    if (
        ultrasonicState ==
        ULTRA_WAIT_FALL
    )
    {
        if (
            digitalRead(
                ULTRASONIC_ECHO
            ) == LOW
        )
        {
            unsigned long duration =
                micros() -
                ultrasonicEchoStart;


            // ------------------------------------------------
            // Convert to centimetres
            // ------------------------------------------------

            ultrasonicDistance =
                duration *
                0.0343 /
                2.0;


            ultrasonicState =
                ULTRA_IDLE;


            sendUltrasonic();


            return;
        }


        // ------------------------------------------------
        // Echo stuck HIGH / timeout
        // ------------------------------------------------

        if (
            micros() -
            ultrasonicEchoStart >
            ULTRASONIC_TIMEOUT
        )
        {
            ultrasonicDistance = -1.0;

            ultrasonicState =
                ULTRA_IDLE;

            sendUltrasonic();

            return;
        }
    }
}


// =====================================================
// ULTRASONIC SERIAL OUTPUT
// =====================================================

void sendUltrasonic()
{
    Serial.print("$ULTRA,");


    if (
        ultrasonicDistance < 0
    )
    {
        Serial.print("-1");
    }
    else
    {
        Serial.print(
            ultrasonicDistance,
            1
        );
    }


    Serial.println("*");
}
