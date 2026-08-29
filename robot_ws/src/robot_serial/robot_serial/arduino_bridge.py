#!/usr/bin/env python3

import glob
import math
import subprocess
import time
import os

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu, Range
from std_msgs.msg import Int64MultiArray, String
from std_srvs.srv import Trigger

import serial


class ArduinoBridge(Node):

    def __init__(self):

        super().__init__('arduino_bridge')

        # SERIAL CONFIG
        self.serial_port = '/dev/ttyACM0'
        self.baud_rate = 115200

        self.ser = None

        self.imu_timeout_sec = 3.0
        self.encoder_timeout_sec = 3.0
        self.ultrasonic_timeout_sec = 1.0

        self.last_imu_time = time.time()
        self.last_encoder_time = time.time()
        self.last_ultrasonic_time = time.time()

        self.open_serial()

        # IMU
        self.imu_pub = self.create_publisher(
            Imu,
            '/imu/data_raw',
            10
        )

        # Wheel encoder ticks
        self.encoder_pub = self.create_publisher(
            Int64MultiArray,
            '/wheel_ticks',
            20
        )

        # Motion state
        self.motion_pub = self.create_publisher(
            String,
            '/motion_state',
            10
        )

        # ULTRASONIC PUBLISHER
        self.ultrasonic_pub = self.create_publisher(
            Range,
            '/ultrasonic',
            10
        )

        # ROS SUBSCRIBERS
        self.create_subscription(
            Twist,
            '/safe_cmd_vel',
            self.cmd_callback,
            10
        )

        # AUTHENTICATION SERVICE
        self.auth_service = self.create_service(
            Trigger,
            '/authenticate_receiver',
            self.authenticate_receiver
        )

        # DELIVERY ARRIVED SERVICE
        self.arrived_service = self.create_service(
            Trigger,
            '/delivery_arrived',
            self.delivery_arrived
        )

        # AUTHENTICATION FAILED SERVICE
        self.failed_service = self.create_service(
            Trigger,
            '/authentication_failed',
            self.authentication_failed
        )

        # TIMERS
        self.timer = self.create_timer(
            0.01,
            self.read_serial
        )

        self.watchdog_timer = self.create_timer(
            1.0,
            self.check_watchdog
        )

        self.recovering = False
        self.last_recovery_time = 0.0
        self.recovery_cooldown = 10.0

        self.get_logger().info(
            "Arduino Bridge Started - "
            "IMU + ENCODER + ULTRASONIC MODE"
        )

    # SERIAL CONNECTION
    def open_serial(self):

        try:

            # Close previous connection
            if self.ser is not None:

                try:
                    self.ser.close()
                except Exception:
                    pass

                self.ser = None

            # USB RESET
            self.get_logger().info(
                "Resetting Arduino USB device..."
            )

            self.reset_usb_device()

            time.sleep(2.0)

            # WAIT FOR SERIAL DEVICE
            device_found = False

            for attempt in range(10):

                if os.path.exists(
                    self.serial_port
                ):

                    device_found = True

                    self.get_logger().info(
                        f"Serial device found: "
                        f"{self.serial_port}"
                    )

                    break

                self.get_logger().info(
                    f"Waiting for "
                    f"{self.serial_port}..."
                )

                time.sleep(0.5)

            if not device_found:

                self.get_logger().error(
                    f"{self.serial_port} did not "
                    "reappear after USB reset"
                )

                return

            # OPEN SERIAL
            self.ser = serial.Serial(
                self.serial_port,
                self.baud_rate,
                timeout=0.05,
                write_timeout=0.2
            )

            # Arduino reset delay
            time.sleep(2.0)

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            self.get_logger().info(
                f"Serial connected: "
                f"{self.serial_port}"
            )

            # START HANDSHAKE
            self.ser.write(
                b"START\n"
            )

            self.ser.flush()

            handshake_start = time.time()

            handshake_ok = False

            while (
                time.time() -
                handshake_start <
                4.0
            ):

                if self.ser.in_waiting <= 0:

                    time.sleep(0.01)

                    continue

                raw = (
                    self.ser.readline()
                    .decode(
                        'utf-8',
                        errors='ignore'
                    )
                    .strip()
                )

                if not raw:
                    continue

                if raw == "MPU_RESET_COMPLETE":

                    handshake_ok = True

                    break

            if handshake_ok:

                self.get_logger().info(
                    "Arduino handshake successful"
                )

            else:

                self.get_logger().warn(
                    "Arduino handshake timeout"
                )

            # Reset stream timers
            now = time.time()

            self.last_imu_time = now
            self.last_encoder_time = now
            self.last_ultrasonic_time = now

        except Exception as e:

            self.get_logger().error(
                f"Serial connection failed: {e}"
            )

            if self.ser is not None:

                try:
                    self.ser.close()
                except Exception:
                    pass


            self.ser = None

    # USB RESET
    def reset_usb_device(self):

        try:

            vid = "04d9"
            pid = "b534"

            devices = glob.glob(
                "/sys/bus/usb/devices/*/idVendor"
            )

            usb_device = None

            for dev in devices:

                try:

                    with open(
                        dev,
                        "r"
                    ) as f:

                        device_vid = (
                            f.read().strip()
                        )

                    product_file = dev.replace(
                        "idVendor",
                        "idProduct"
                    )

                    with open(
                        product_file,
                        "r"
                    ) as f:

                        device_pid = (
                            f.read().strip()
                        )

                    if (
                        device_vid == vid and
                        device_pid == pid
                    ):

                        usb_device = dev.replace(
                            "/idVendor",
                            ""
                        )

                        break

                except Exception:

                    pass

            if usb_device is None:
                return

            device_name = (
                usb_device.split("/")[-1]
            )

            subprocess.run(
                [
                    "sudo",
                    "sh",
                    "-c",
                    f"echo {device_name} > "
                    "/sys/bus/usb/drivers/usb/unbind"
                ],
                check=False
            )

            time.sleep(1)

            subprocess.run(
                [
                    "sudo",
                    "sh",
                    "-c",
                    f"echo {device_name} > "
                    "/sys/bus/usb/drivers/usb/bind"
                ],
                check=False
            )

            time.sleep(2)

        except Exception as e:

            self.get_logger().warn(
                f"USB reset failed: {e}"
            )

    # SAFE CMD_VEL -> ARDUINO
    def cmd_callback(self, msg):

        if self.ser is None:
            return

        linear = msg.linear.x
        angular = msg.angular.z

        command = (
            f"V,{linear:.3f},{angular:.3f}\n"
        )

        try:

            self.ser.write(
                command.encode('utf-8')
            )

        except Exception as e:

            self.get_logger().error(
                f"Serial write failed: {e}"
            )

            self.close_serial()

    # AUTHENTICATION HANDSHAKE
    def authenticate_receiver(self, request, response):

        if self.ser is None:

            response.success = False

            response.message = (
                "Arduino serial connection unavailable"
            )

            self.get_logger().error(
                "Authentication failed: "
                "Arduino is not connected"
            )

            return response

        try:

            self.get_logger().info(
                "Sending AUTHENTICATED to Arduino..."
            )

            # Send authentication command
            self.ser.write(
                b"AUTHENTICATED\n"
            )

            self.ser.flush()

            # Wait for Arduino acknowledgement
            timeout = 3.0

            start_time = time.time()

            while (
                time.time() - start_time
                < timeout
            ):

                if self.ser.in_waiting <= 0:

                    time.sleep(0.01)

                    continue

                raw = (
                    self.ser.readline()
                    .decode(
                        'utf-8',
                        errors='ignore'
                    )
                    .strip()
                )

                if not raw:

                    continue

                # Authentication acknowledgement
                if raw == "AUTH_ACK":

                    self.get_logger().info(
                        "Authentication handshake successful"
                    )

                    response.success = True

                    response.message = (
                        "Authentication handshake successful"
                    )

                    return response

                # Keep processing normal robot data
                if (
                    raw.startswith("$IMU,") and
                    raw.endswith("*")
                ):

                    self.process_imu(raw)

                elif (
                    raw.startswith("$ENC,") and
                    raw.endswith("*")
                ):

                    self.process_encoder(raw)

                elif (
                    raw.startswith("$ULTRA,") and
                    raw.endswith("*")
                ):

                    self.process_ultrasonic(raw)

                elif raw == "READY":

                    self.get_logger().info(
                        "Arduino READY"
                    )

                elif raw == "MPU_RESET_COMPLETE":

                    self.get_logger().info(
                        "MPU reset complete"
                    )

                elif raw == "ENCODERS_RESET":

                    self.get_logger().info(
                        "Encoders reset"
                    )

            # Timeout
            self.get_logger().error(
                "Authentication handshake timeout"
            )

            response.success = False

            response.message = (
                "Arduino did not acknowledge authentication"
            )

            return response

        except Exception as e:

            self.get_logger().error(
                f"Authentication handshake failed: {e}"
            )

            response.success = False

            response.message = (
                f"Authentication failed: {e}"
            )

            return response

    # DELIVERY ARRIVED -> BLUE LED
    def delivery_arrived(self, request, response):

        if self.ser is None:

            response.success = False

            response.message = (
                "Arduino serial connection unavailable"
            )

            self.get_logger().error(
                "Cannot set ARRIVED LED: "
                "Arduino is not connected"
            )

            return response

        try:

            self.get_logger().info(
                "Sending DELIVERY_ARRIVED to Arduino..."
            )

            # Send command
            self.ser.write(
                b"DELIVERY_ARRIVED\n"
            )

            self.ser.flush()

            # Wait for acknowledgement
            timeout = 3.0

            start_time = time.time()

            while (
                time.time() - start_time
                < timeout
            ):

                if self.ser.in_waiting <= 0:

                    time.sleep(0.01)

                    continue

                raw = (
                    self.ser.readline()
                    .decode(
                        'utf-8',
                        errors='ignore'
                    )
                    .strip()
                )

                if not raw:

                    continue

                # Expected acknowledgement
                if raw == "ARRIVED_ACK":

                    self.get_logger().info(
                        "Delivery-arrived LED successful"
                    )

                    response.success = True

                    response.message = (
                        "Delivery arrived - LED set to blue"
                    )

                    return response

                # Keep processing normal robot data
                if (
                    raw.startswith("$IMU,") and
                    raw.endswith("*")
                ):

                    self.process_imu(raw)

                elif (
                    raw.startswith("$ENC,") and
                    raw.endswith("*")
                ):

                    self.process_encoder(raw)

                elif (
                    raw.startswith("$ULTRA,") and
                    raw.endswith("*")
                ):

                    self.process_ultrasonic(raw)

            # Timeout
            self.get_logger().error(
                "Delivery-arrived LED handshake timeout"
            )

            response.success = False

            response.message = (
                "Arduino did not acknowledge DELIVERY_ARRIVED"
            )

            return response

        except Exception as e:

            self.get_logger().error(
                f"Delivery-arrived LED failed: {e}"
            )

            response.success = False

            response.message = (
                f"Delivery-arrived LED failed: {e}"
            )

            return response

    # AUTHENTICATION FAILED - RED LED
    def authentication_failed(self, request, response):

        if self.ser is None:

            response.success = False

            response.message = (
                "Arduino serial connection unavailable"
            )

            self.get_logger().error(
                "Cannot set authentication error LED: "
                "Arduino is not connected"
            )

            return response


        try:

            self.get_logger().info(
                "Sending AUTH_FAILED to Arduino..."
            )

            # Send command
            self.ser.write(
                b"AUTH_FAILED\n"
            )

            self.ser.flush()

            # Wait for acknowledgement
            timeout = 3.0

            start_time = time.time()


            while (
                time.time() - start_time
                < timeout
            ):

                if self.ser.in_waiting <= 0:

                    time.sleep(0.01)

                    continue


                raw = (
                    self.ser.readline()
                    .decode(
                        'utf-8',
                        errors='ignore'
                    )
                    .strip()
                )


                if not raw:

                    continue

                # Expected acknowledgement
                if raw == "AUTH_FAILED_ACK":

                    self.get_logger().info(
                        "Authentication error LED successful"
                    )


                    response.success = True

                    response.message = (
                        "Authentication failed - LED set to red"
                    )

                    return response

                # Keep processing normal robot data
                if (
                    raw.startswith("$IMU,") and
                    raw.endswith("*")
                ):

                    self.process_imu(raw)

                elif (
                    raw.startswith("$ENC,") and
                    raw.endswith("*")
                ):
                    self.process_encoder(raw)

                elif (
                    raw.startswith("$ULTRA,") and
                    raw.endswith("*")
                ):
                    self.process_ultrasonic(raw)

            # Timeout
            self.get_logger().error(
                "Authentication-failed LED handshake timeout"
            )

            response.success = False

            response.message = (
                "Arduino did not acknowledge AUTH_FAILED"
            )

            return response

        except Exception as e:

            self.get_logger().error(
                f"Authentication error LED failed: {e}"
            )

            response.success = False

            response.message = (
                f"Authentication error LED failed: {e}"
            )

            return response
        
    # SERIAL READER
    def read_serial(self):

        if self.ser is None:

            return

        try:

            lines_processed = 0

            while (
                self.ser.in_waiting > 0 and
                lines_processed < 30
            ):

                raw = (
                    self.ser.readline()
                    .decode(
                        'utf-8',
                        errors='ignore'
                    )
                    .strip()
                )

                lines_processed += 1

                if not raw:

                    continue

                # IMU
                if (
                    raw.startswith("$IMU,") and
                    raw.endswith("*")
                ):

                    self.process_imu(raw)

                # ENCODER
                elif (
                    raw.startswith("$ENC,") and
                    raw.endswith("*")
                ):
                    self.process_encoder(raw)

                # ULTRASONIC
                elif (
                    raw.startswith("$ULTRA,") and
                    raw.endswith("*")
                ):
                    self.process_ultrasonic(raw)

                # STATUS
                elif raw == "READY":

                    self.get_logger().info(
                        "Arduino READY"
                    )

                elif raw == "MPU_RESET_COMPLETE":

                    self.get_logger().info(
                        "MPU reset complete"
                    )

                elif raw == "ENCODERS_RESET":

                    self.get_logger().info(
                        "Encoders reset"
                    )

        except (
            serial.SerialException,
            OSError
        ) as e:

            self.get_logger().error(
                f"Serial disconnected: {e}"
            )

            self.close_serial()


        except Exception as e:

            self.get_logger().warn(
                f"Serial parse error: {e}"
            )

    # PROCESS IMU
    def process_imu(self, raw):

        try:

            data = (
                raw
                .replace("$IMU,", "")
                .replace("*", "")
            )

            parts = data.split(",")

            if len(parts) != 6:

                return

            ax, ay, az, gx, gy, gz = map(
                float,
                parts
            )

            imu = Imu()

            imu.header.stamp = (
                self.get_clock()
                .now()
                .to_msg()
            )

            imu.header.frame_id = "imu_link"

            # ACCELERATION
            g = 9.80665

            imu.linear_acceleration.x = (
                ax / 16384.0
            ) * g

            imu.linear_acceleration.y = (
                ay / 16384.0
            ) * g

            imu.linear_acceleration.z = (
                az / 16384.0
            ) * g

            # GYROSCOPE
            deg_to_rad = math.pi / 180.0

            imu.angular_velocity.x = (
                gx / 131.0
            ) * deg_to_rad

            imu.angular_velocity.y = (
                gy / 131.0
            ) * deg_to_rad

            imu.angular_velocity.z = (
                gz / 131.0
            ) * deg_to_rad

            # No orientation from Arduino

            imu.orientation_covariance[0] = -1.0

            imu.angular_velocity_covariance = [
                0.05, 0.0, 0.0,
                0.0, 0.05, 0.0,
                0.0, 0.0, 0.03
            ]

            imu.linear_acceleration_covariance = [
                0.20, 0.0, 0.0,
                0.0, 0.20, 0.0,
                0.0, 0.0, 0.20
            ]

            self.imu_pub.publish(
                imu
            )

            self.last_imu_time = time.time()

        except Exception as e:

            self.get_logger().warn(
                f"Bad IMU packet: "
                f"{raw} - {e}"
            )

    # PROCESS ENCODER
    def process_encoder(self, raw):

        try:

            data = (
                raw
                .replace("$ENC,", "")
                .replace("*", "")
            )

            parts = data.split(",")

            if len(parts) != 2:

                return

            left_ticks = int(
                parts[0]
            )

            right_ticks = int(
                parts[1]
            )

            msg = Int64MultiArray()

            msg.data = [
                left_ticks,
                right_ticks
            ]

            self.encoder_pub.publish(
                msg
            )

            self.last_encoder_time = (
                time.time()
            )

        except Exception as e:

            self.get_logger().warn(
                f"Bad encoder packet: "
                f"{raw} - {e}"
            )

    # PROCESS ULTRASONIC
    def process_ultrasonic(self, raw):

        try:

            data = (
                raw
                .replace("$ULTRA,", "")
                .replace("*", "")
                .strip()
            )

            distance_cm = float(data)

            # ROS RANGE MESSAGE
            msg = Range()

            msg.header.stamp = (
                self.get_clock()
                .now()
                .to_msg()
            )

            msg.header.frame_id = (
                "ultrasonic_link"
            )

            # HC-SR04 style ultrasonic sensor
            msg.radiation_type = (
                Range.ULTRASOUND
            )

            msg.field_of_view = (
                math.radians(15.0)
            )

            msg.min_range = 0.02
            msg.max_range = 4.0

            # INVALID READING
            if distance_cm < 0:

                msg.range = float('nan')

            else:

                msg.range = (
                    distance_cm / 100.0
                )

            self.ultrasonic_pub.publish(
                msg
            )

            self.last_ultrasonic_time = (
                time.time()
            )

        except Exception as e:

            self.get_logger().warn(
                f"Bad ultrasonic packet: "
                f"{raw} - {e}"
            )

    # WATCHDOG
    def check_watchdog(self):

        now = time.time()

        # SERIAL DISCONNECTED
        if self.ser is None:

            if (
                not self.recovering and
                now - self.last_recovery_time >
                self.recovery_cooldown
            ):

                self.get_logger().warn(
                    "Arduino disconnected - "
                    "performing USB recovery"
                )

                self.recovering = True

                try:

                    self.open_serial()

                finally:

                    self.last_recovery_time = (
                        time.time()
                    )

                    self.recovering = False

            return

        # STREAM TIMEOUTS
        imu_timeout = (
            now -
            self.last_imu_time >
            self.imu_timeout_sec
        )

        encoder_timeout = (
            now -
            self.last_encoder_time >
            self.encoder_timeout_sec
        )

        ultrasonic_timeout = (
            now -
            self.last_ultrasonic_time >
            self.ultrasonic_timeout_sec
        )

        # LOG ULTRASONIC TIMEOUT
        if ultrasonic_timeout:

            self.get_logger().warn(
                "Ultrasonic stream timeout"
            )

        # FULL RECOVERY
        if imu_timeout and encoder_timeout:

            if (
                not self.recovering and
                now - self.last_recovery_time >
                self.recovery_cooldown
            ):

                self.get_logger().error(
                    "IMU + encoder streams stopped - "
                    "performing USB reset"
                )

                self.recovering = True

                try:

                    self.close_serial()
                    self.open_serial()

                finally:

                    self.last_recovery_time = (
                        time.time()
                    )

                    self.recovering = False

        elif imu_timeout:

            self.get_logger().warn(
                "IMU stream timeout - "
                "encoder still alive"
            )

        elif encoder_timeout:

            self.get_logger().warn(
                "Encoder stream timeout - "
                "IMU still alive"
            )

    # CLOSE SERIAL
    def close_serial(self):

        if self.ser is not None:

            try:

                self.ser.close()

            except Exception:

                pass


        self.ser = None

    # DESTROY
    def destroy_node(self):

        if self.ser is not None:

            try:

                self.ser.write(
                    b"STOP\n"
                )

            except Exception:

                pass

        self.close_serial()

        super().destroy_node()

# MAIN
def main(args=None):

    rclpy.init(
        args=args
    )

    node = ArduinoBridge()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':

    main()