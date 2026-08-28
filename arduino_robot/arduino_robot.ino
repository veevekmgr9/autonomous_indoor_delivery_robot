#include <Wire.h>
#include <Adafruit_NeoPixel.h>

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

#define ULTRASONIC_TRIG 13
#define ULTRASONIC_ECHO 12

#define LEFT_ENCODER  A1
#define RIGHT_ENCODER A2

#define RGB_PIN 4
#define RGB_COUNT 1


// =====================================================
// MOTOR SPEED SETTINGS
// =====================================================

// Normal forward speed
#define FORWARD_PWM 140

// Reverse speed
#define REVERSE_PWM 140

// Extra power for turning on rough surfaces
#define ROTATION_PWM 250


// =====================================================
// MOTOR CONTROL
// =====================================================

float WHEEL_BASE = 0.125;          // metres
float MAX_LINEAR_SPEED = 0.20;     // m/s


// =====================================================
// ENCODERS
// =====================================================

volatile long leftTicks = 0;
volatile long rightTicks = 0;


// Direction is taken from the motor command.
// +1 = forward
// -1 = reverse
//  0 = stopped

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

unsigned long lastUltrasonicTrigger = 0;

const unsigned long ULTRASONIC_INTERVAL = 100;
// 10 Hz


enum UltrasonicState
{
    ULTRA_IDLE,
    ULTRA_WAIT_RISE,
    ULTRA_WAIT_FALL
};

UltrasonicState ultrasonicState = ULTRA_IDLE;

unsigned long ultrasonicEchoStart = 0;

float ultrasonicDistance = -1.0;

const unsigned long ULTRASONIC_TIMEOUT = 25000;
// 25 ms


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
// RGB LED
// =====================================================

Adafruit_NeoPixel rgb(
    RGB_COUNT,
    RGB_PIN,
    NEO_GRB + NEO_KHZ800
);


// Authentication LED state

unsigned long ledStateStartedAt = 0;

const unsigned long AUTH_LED_DURATION = 5000;

bool temporaryLedState = false;


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


    // I2C

    i2cBusRecovery();

    Wire.begin();

    Wire.setWireTimeout(
        3000,
        true
    );


    // MPU6050

    Wire.beginTransmission(MPU_addr);

    Wire.write(0x6B);
    Wire.write(0x00);

    Wire.endTransmission(true);


    // Motor pins

    pinMode(PWMA, OUTPUT);
    pinMode(PWMB, OUTPUT);

    pinMode(AIN1, OUTPUT);
    pinMode(AIN2, OUTPUT);

    pinMode(BIN1, OUTPUT);
    pinMode(BIN2, OUTPUT);

    pinMode(STBY, OUTPUT);

    digitalWrite(STBY, HIGH);

    stopRobot();


    // Encoders

    pinMode(
        LEFT_ENCODER,
        INPUT_PULLUP
    );

    pinMode(
        RIGHT_ENCODER,
        INPUT_PULLUP
    );

    lastPortC = PINC;

    PCICR |= (1 << PCIE1);

    // A1 = PC1
    PCMSK1 |= (1 << PCINT9);

    // A2 = PC2
    PCMSK1 |= (1 << PCINT10);

    leftTicks = 0;
    rightTicks = 0;


    // Ultrasonic

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


    // RGB LED

    rgb.begin();

    rgb.setBrightness(50);

    rgb.clear();

    rgb.show();

    setWaitingLED();


    rosConnected = false;

    Serial.println("READY");
}


// =====================================================
// MAIN LOOP
// =====================================================

void loop()
{
    // -------------------------------------------------
    // Read commands from Raspberry Pi
    // -------------------------------------------------

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


    // -------------------------------------------------
    // IMU
    // -------------------------------------------------

    if (
        rosConnected &&
        millis() - lastImuTime >= IMU_INTERVAL
    )
    {
        lastImuTime = millis();

        sendIMU();
    }


    // -------------------------------------------------
    // Encoders
    // -------------------------------------------------

    if (
        rosConnected &&
        millis() - lastEncoderTime >= ENCODER_INTERVAL
    )
    {
        lastEncoderTime = millis();

        sendEncoders();
    }


    // -------------------------------------------------
    // Ultrasonic
    // -------------------------------------------------

    if (rosConnected)
    {
        updateUltrasonic();
    }


    // -------------------------------------------------
    // Temporary authentication LED
    // -------------------------------------------------

    if (
        temporaryLedState &&
        millis() - ledStateStartedAt >=
        AUTH_LED_DURATION
    )
    {
        setWaitingLED();

        temporaryLedState = false;
    }
}


// =====================================================
// COMMAND PROCESSOR
// =====================================================

void processCommand(String cmd)
{
    // -------------------------------------------------
    // START
    // -------------------------------------------------

    if (cmd == "START")
    {
        resetMPU();

        rosConnected = true;

        leftEncoderDirection = 0;
        rightEncoderDirection = 0;

        ultrasonicState = ULTRA_IDLE;

        ultrasonicDistance = -1.0;

        lastUltrasonicTrigger = millis();

        Serial.println(
            "MPU_RESET_COMPLETE"
        );

        return;
    }


    // -------------------------------------------------
    // VELOCITY COMMAND
    //
    // V,linear,angular
    //
    // Example:
    //
    // V,0.08,0.0
    // -------------------------------------------------

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


    // -------------------------------------------------
    // STOP
    // -------------------------------------------------

    if (cmd == "STOP")
    {
        stopRobot();

        return;
    }


    // -------------------------------------------------
    // DELIVERY ARRIVED
    // -------------------------------------------------

    if (cmd == "DELIVERY_ARRIVED")
    {
        setWaitingLED();

        temporaryLedState = false;

        Serial.println("ARRIVED_ACK");

        return;
    }


    // -------------------------------------------------
    // AUTHENTICATED
    // -------------------------------------------------

    if (cmd == "AUTHENTICATED")
    {
        setAuthenticatedLED();

        ledStateStartedAt = millis();

        temporaryLedState = true;

        Serial.println("AUTH_ACK");

        return;
    }


    // -------------------------------------------------
    // AUTHENTICATION FAILED
    // -------------------------------------------------

    if (cmd == "AUTH_FAILED")
    {
        setFailedLED();

        ledStateStartedAt = millis();

        temporaryLedState = true;

        Serial.println("AUTH_FAILED_ACK");

        return;
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


    // Reset signal paths

    Wire.beginTransmission(MPU_addr);

    Wire.write(0x68);
    Wire.write(0x07);

    Wire.endTransmission(true);

    delay(100);


    // Wake MPU

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
        ax =
            Wire.read() << 8 |
            Wire.read();

        ay =
            Wire.read() << 8 |
            Wire.read();

        az =
            Wire.read() << 8 |
            Wire.read();


        // Skip temperature

        Wire.read();
        Wire.read();


        gx =
            Wire.read() << 8 |
            Wire.read();

        gy =
            Wire.read() << 8 |
            Wire.read();

        gz =
            Wire.read() << 8 |
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
    // -------------------------------------------------
    // Reduce the turning response slightly.
    // This keeps normal navigation smooth.
    // -------------------------------------------------

    angular *= 1.50;


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
    // Remember wheel directions for encoders
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
    // Decide which PWM setting to use
    // -------------------------------------------------

    int pwmLimit;


    // Pure rotation
    if (
        abs(linear) < 0.01 &&
        abs(angular) > 0.01
    )
    {
        pwmLimit = ROTATION_PWM;
    }


    // Forward
    else if (linear > 0.01)
    {
        pwmLimit = FORWARD_PWM;
    }


    // Reverse
    else if (linear < -0.01)
    {
        pwmLimit = REVERSE_PWM;
    }


    // No movement
    else
    {
        pwmLimit = 0;
    }


    // -------------------------------------------------
    // Convert wheel speed to PWM
    // -------------------------------------------------

    int leftPWM = 0;
    int rightPWM = 0;

    if (pwmLimit > 0)
    {
        leftPWM =
            abs(
                leftSpeed /
                MAX_LINEAR_SPEED *
                pwmLimit
            );

        rightPWM =
            abs(
                rightSpeed /
                MAX_LINEAR_SPEED *
                pwmLimit
            );


        leftPWM =
            constrain(
                leftPWM,
                0,
                pwmLimit
            );

        rightPWM =
            constrain(
                rightPWM,
                0,
                pwmLimit
            );
    }


    // -------------------------------------------------
    // Motor directions
    // -------------------------------------------------

    // Left motor

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


    // Right motor

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


    // -------------------------------------------------
    // Minimum PWM
    //
    // This helps the motors start moving when the
    // requested speed is very small.
    // -------------------------------------------------

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


    // -------------------------------------------------
    // Apply PWM
    // -------------------------------------------------

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


    leftEncoderDirection = 0;
    rightEncoderDirection = 0;
}


// =====================================================
// ENCODER INTERRUPT
// =====================================================

ISR(PCINT1_vect)
{
    byte currentPortC = PINC;


    // Left encoder

    if (
        (lastPortC & _BV(PC1)) &&
        !(currentPortC & _BV(PC1))
    )
    {
        leftTicks += leftEncoderDirection;
    }


    // Right encoder

    if (
        (lastPortC & _BV(PC2)) &&
        !(currentPortC & _BV(PC2))
    )
    {
        rightTicks += rightEncoderDirection;
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


// =====================================================
// ULTRASONIC
// =====================================================

void updateUltrasonic()
{
    unsigned long now = micros();


    // -------------------------------------------------
    // Start a new measurement
    // -------------------------------------------------

    if (ultrasonicState == ULTRA_IDLE)
    {
        if (
            millis() -
            lastUltrasonicTrigger >=
            ULTRASONIC_INTERVAL
        )
        {
            lastUltrasonicTrigger = millis();


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


            ultrasonicState =
                ULTRA_WAIT_RISE;

            ultrasonicEchoStart = now;
        }

        return;
    }


    // -------------------------------------------------
    // Wait for echo HIGH
    // -------------------------------------------------

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


    // -------------------------------------------------
    // Wait for echo LOW
    // -------------------------------------------------

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


            ultrasonicDistance =
                duration *
                0.0343 /
                2.0;


            ultrasonicState =
                ULTRA_IDLE;

            sendUltrasonic();

            return;
        }


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
// ULTRASONIC OUTPUT
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


// =====================================================
// RGB LED
// =====================================================

void setRobotRGB(
    uint8_t r,
    uint8_t g,
    uint8_t b
)
{
    rgb.setPixelColor(
        0,
        rgb.Color(r, g, b)
    );

    rgb.show();
}


void setWaitingLED()
{
    setRobotRGB(
        0,
        0,
        80
    );
}


void setAuthenticatedLED()
{
    setRobotRGB(
        0,
        120,
        0
    );
}


void setFailedLED()
{
    setRobotRGB(
        120,
        0,
        0
    );
}


void setLEDOff()
{
    setRobotRGB(
        0,
        0,
        0
    );
}
