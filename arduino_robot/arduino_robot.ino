#include <Wire.h>

const int MPU_addr = 0x68;

// ---------------- MOTOR PINS ----------------
#define PWMA 5
#define PWMB 6
#define AIN1 7
#define AIN2 11
#define BIN1 8
#define BIN2 10
#define STBY 3

int motorSpeed = 60;

// ---------------- IMU DATA ----------------
int16_t ax, ay, az;
int16_t gx, gy, gz;

unsigned long lastImuTime = 0;
const unsigned long IMU_INTERVAL = 20; // 50Hz (20ms)

String inputBuffer = "";
bool rosConnected = false; // Controlled strictly by ROS2 node

// =====================================================
// I2C BUS RECOVERY
// If a DTR-triggered reset lands mid I2C-transaction, the MPU6050
// can be left holding SDA low (clock-stretching / partial ACK).
// Wire.begin() -> beginTransmission() will then hang forever, since
// Wire.setWireTimeout() only guards against the master (us) hanging,
// not a slave holding the bus. This bit-bangs SCL to force the slave
// to release SDA before the Wire library ever touches the bus.
// =====================================================
void i2cBusRecovery()
{
    pinMode(A5, INPUT); // SCL on Uno
    pinMode(A4, INPUT); // SDA on Uno

    if (digitalRead(A4) == LOW) // SDA stuck low -> bus is jammed
    {
        pinMode(A5, OUTPUT);
        for (int i = 0; i < 9; i++)
        {
            digitalWrite(A5, HIGH);
            delayMicroseconds(5);
            digitalWrite(A5, LOW);
            delayMicroseconds(5);
        }
        pinMode(A5, INPUT); // release, let Wire.begin() take over
    }
}

void setup()
{
    Serial.begin(115200);

    i2cBusRecovery();

    Wire.begin();
    Wire.setWireTimeout(3000, true); // Auto-recovers a locked I2C bus on timeout

    // Initialize MPU6050
    Wire.beginTransmission(MPU_addr);
    Wire.write(0x6B);
    Wire.write(0);
    Wire.endTransmission(true);

    // ---------------- MOTOR SETUP ----------------
    pinMode(PWMA, OUTPUT);   pinMode(PWMB, OUTPUT);
    pinMode(AIN1, OUTPUT);   pinMode(AIN2, OUTPUT);
    pinMode(BIN1, OUTPUT);   pinMode(BIN2, OUTPUT);
    pinMode(STBY, OUTPUT);

    digitalWrite(STBY, HIGH);
    stopRobot();

    // rosConnected always starts false after any reset (power-on,
    // watchdog, or DTR-triggered) so the ROS side must always
    // re-handshake with START before it will see IMU data again.
    rosConnected = false;

    Serial.println("READY");
}

void loop()
{
    // ---------------- NON-BLOCKING COMMAND RECEIVE ----------------
    while (Serial.available() > 0)
    {
        char inChar = (char)Serial.read();

        if (inChar == '\n' || inChar == '\r')
        {
            inputBuffer.trim();
            if (inputBuffer.length() > 0) {
                processCommand(inputBuffer);
            }
            inputBuffer = "";
        }
        else
        {
            inputBuffer += inChar;
        }
    }

    // ---------------- IMU STREAM (50Hz) ----------------
    if (rosConnected && (millis() - lastImuTime >= IMU_INTERVAL))
    {
        lastImuTime = millis();
        sendIMU();
    }
}

// =====================================================
// COMMAND PROCESSOR
// =====================================================
void processCommand(String cmd)
{
    if (cmd == "START") {
        resetMPU();            // Ensure the MPU6050 registers are completely clean
        rosConnected = true;   // Instantly start streaming data packets
        Serial.println("MPU_RESET_COMPLETE"); // ACK so ROS side can confirm sync
        return;
    }

    if (cmd == "W") forward();
    else if (cmd == "X") backward();
    else if (cmd == "A") left();
    else if (cmd == "D") right();
    else if (cmd == "S") stopRobot();
}

void resetMPU()
{
    // 1. Issue a full device reset via PWR_MGMT_1 (Bit 7 = 1)
    Wire.beginTransmission(MPU_addr);
    Wire.write(0x6B);
    Wire.write(0x80);
    Wire.endTransmission(true);

    delay(100); // Wait for the MPU6050 internal registers to reset cleanly

    // 2. Reset the signal paths for Gyro, Accel, and Temp (Bits 2, 1, 0 = 1)
    Wire.beginTransmission(MPU_addr);
    Wire.write(0x68);
    Wire.write(0x07);
    Wire.endTransmission(true);

    delay(100); // Give the sensors a moment to clear their internal pipelines

    // 3. Wake the MPU6050 up out of sleep mode and set clock source to internal 8MHz
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
    // Safety check: Avoid buffer blocking if ROS2 disconnects
//    if (Serial.availableForWrite() < 40) {
//        rosConnected = false; // Kill stream until ROS2 flushes buffer
//        return;
//    }

    Wire.beginTransmission(MPU_addr);
    Wire.write(0x3B);
    if (Wire.endTransmission(false) != 0) return;

    Wire.requestFrom(MPU_addr, 14, true);
    if (Wire.available() >= 14) {
        ax = Wire.read() << 8 | Wire.read();
        ay = Wire.read() << 8 | Wire.read();
        az = Wire.read() << 8 | Wire.read();
        Wire.read(); Wire.read(); // Skip temp registers
        gx = Wire.read() << 8 | Wire.read();
        gy = Wire.read() << 8 | Wire.read();
        gz = Wire.read() << 8 | Wire.read();

        Serial.print("$IMU,");
        Serial.print(ax); Serial.print(",");
        Serial.print(ay); Serial.print(",");
        Serial.print(az); Serial.print(",");
        Serial.print(gx); Serial.print(",");
        Serial.print(gy); Serial.print(",");
        Serial.print(gz);
        Serial.println("*");
    }
}

// =====================================================
// MOTOR FUNCTIONS
// =====================================================
void forward() {
    analogWrite(PWMA, motorSpeed); analogWrite(PWMB, motorSpeed);
    digitalWrite(AIN1, HIGH); digitalWrite(AIN2, LOW);
    digitalWrite(BIN1, HIGH); digitalWrite(BIN2, LOW);
}
void backward() {
    analogWrite(PWMA, motorSpeed); analogWrite(PWMB, motorSpeed);
    digitalWrite(AIN1, LOW); digitalWrite(AIN2, HIGH);
    digitalWrite(BIN1, LOW); digitalWrite(BIN2, HIGH);
}
void left() {
    analogWrite(PWMA, motorSpeed); analogWrite(PWMB, motorSpeed);
    digitalWrite(AIN1, LOW); digitalWrite(AIN2, HIGH);
    digitalWrite(BIN1, HIGH); digitalWrite(BIN2, LOW);
}
void right() {
    analogWrite(PWMA, motorSpeed); analogWrite(PWMB, motorSpeed);
    digitalWrite(AIN1, HIGH); digitalWrite(AIN2, LOW);
    digitalWrite(BIN1, LOW); digitalWrite(BIN2, HIGH);
}
void stopRobot() {
    analogWrite(PWMA, 0); analogWrite(PWMB, 0);
    digitalWrite(AIN1, LOW); digitalWrite(AIN2, LOW);
    digitalWrite(BIN1, LOW); digitalWrite(BIN2, LOW);
}
