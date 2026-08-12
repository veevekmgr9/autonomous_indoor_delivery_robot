#!/usr/bin/env python3

import glob
import math
import subprocess
import time
import os

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu
from std_msgs.msg import Int64MultiArray, String

import serial


class ArduinoBridge(Node):

    def __init__(self):
        super().__init__('arduino_bridge')

        # =====================================================
        # SERIAL CONFIG
        # =====================================================

        self.serial_port = '/dev/ttyACM0'
        self.baud_rate = 115200

        self.ser = None

        self.imu_timeout_sec = 3.0
        self.last_imu_time = time.time()

        self.last_encoder_time = time.time()

        self.open_serial()


        # =====================================================
        # ROS PUBLISHERS
        # =====================================================

        self.imu_pub = self.create_publisher(
            Imu,
            '/imu/data_raw',
            10
        )

        self.encoder_pub = self.create_publisher(
            Int64MultiArray,
            '/wheel_ticks',
            20
        )

        self.motion_pub = self.create_publisher(
            String,
            '/motion_state',
            10
        )


        # =====================================================
        # ROS SUBSCRIBERS
        # =====================================================

        self.create_subscription(
            Twist,
            '/safe_cmd_vel',
            self.cmd_callback,
            10
        )


        # =====================================================
        # TIMERS
        # =====================================================

        # Serial polling
        self.timer = self.create_timer(
            0.01,
            self.read_serial
        )

        # Serial/IMU watchdog
        self.watchdog_timer = self.create_timer(
            1.0,
            self.check_watchdog
        )

        self.recovering = False
        self.last_recovery_time = 0.0

        self.recovery_cooldown = 10.0

        self.get_logger().info(
            "Arduino Bridge Started - IMU + ENCODER MODE"
        )


    # =========================================================
    # SERIAL CONNECTION
    # =========================================================

    def open_serial(self):

        try:
            # Close previous serial connection
            if self.ser is not None:
                try:
                    self.ser.close()
                except Exception:
                    pass

                self.ser = None

            # =============================================
            # USB RESET
            # =============================================

            self.get_logger().info(
                "Resetting Arduino USB device..."
            )

            self.reset_usb_device()

            # Give Linux time to recreate ttyACM0
            time.sleep(2.0)

            # =============================================
            # WAIT FOR SERIAL DEVICE
            # =============================================

            device_found = False

            for attempt in range(10):

                if os.path.exists(self.serial_port):

                    device_found = True

                    self.get_logger().info(
                        f"Serial device found: "
                        f"{self.serial_port}"
                    )

                    break

                self.get_logger().info(
                    f"Waiting for {self.serial_port}..."
                )

                time.sleep(0.5)


            if not device_found:

                self.get_logger().error(
                    f"{self.serial_port} did not reappear "
                    "after USB reset"
                )

                return


            # =============================================
            # OPEN SERIAL
            # =============================================

            self.ser = serial.Serial(
                self.serial_port,
                self.baud_rate,
                timeout=0.05,
                write_timeout=0.2
            )

            # Opening serial resets many Arduino boards.
            # Give setup() time to finish.
            time.sleep(2.0)


            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()


            self.get_logger().info(
                f"Serial connected: {self.serial_port}"
            )


            # =============================================
            # START HANDSHAKE
            # =============================================

            self.ser.write(b"START\n")
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


                # self.get_logger().info(
                #     f"Arduino: {raw}"
                # )


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


            self.last_imu_time = time.time()

            self.last_encoder_time = time.time()


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


    # =========================================================
    # OPTIONAL USB RESET
    # =========================================================

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

                    with open(dev, "r") as f:
                        device_vid = f.read().strip()

                    product_file = dev.replace(
                        "idVendor",
                        "idProduct"
                    )

                    with open(product_file, "r") as f:
                        device_pid = f.read().strip()

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


            device_name = usb_device.split("/")[-1]


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


    # =========================================================
    # ROS CMD_VEL -> ARDUINO
    # =========================================================

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


    # =========================================================
    # SERIAL READER
    # =========================================================

    def read_serial(self):

        if self.ser is None:
            return

        try:

            # Read several available packets per callback
            # so IMU traffic does not delay encoder packets.

            lines_processed = 0

            while (
                self.ser.in_waiting > 0 and
                lines_processed < 20
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


    # =========================================================
    # PROCESS IMU
    # =========================================================

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


            # MPU6050 default accelerometer:
            # +/-2g = 16384 LSB/g

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


            # MPU6050 default gyro:
            # +/-250 deg/s = 131 LSB/(deg/s)

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


            # No orientation estimate is produced by
            # this Arduino firmware.

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


            self.imu_pub.publish(imu)

            self.last_imu_time = time.time()


        except Exception as e:

            self.get_logger().warn(
                f"Bad IMU packet: {raw} - {e}"
            )


    # =========================================================
    # PROCESS ENCODERS
    # =========================================================

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


            left_ticks = int(parts[0])
            right_ticks = int(parts[1])


            msg = Int64MultiArray()

            msg.data = [
                left_ticks,
                right_ticks
            ]


            self.encoder_pub.publish(msg)

            self.last_encoder_time = time.time()


        except Exception as e:

            self.get_logger().warn(
                f"Bad encoder packet: {raw} - {e}"
            )


    # =========================================================
    # WATCHDOG
    # =========================================================
    def check_watchdog(self):

        now = time.time()


        # ---------------------------------------------
        # SERIAL COMPLETELY DISCONNECTED
        # ---------------------------------------------

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


        # ---------------------------------------------
        # CHECK BOTH STREAMS
        # ---------------------------------------------

        imu_timeout = (
            now -
            self.last_imu_time >
            self.imu_timeout_sec
        )

        encoder_timeout = (
            now -
            self.last_encoder_time >
            self.imu_timeout_sec
        )


        # Only perform a full USB recovery when BOTH
        # streams have stopped.
        #
        # This prevents an MPU issue from unnecessarily
        # destroying a working encoder connection.

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

    def close_serial(self):

        if self.ser is not None:

            try:
                self.ser.close()
            except Exception:
                pass

        self.ser = None


    def destroy_node(self):

        if self.ser is not None:

            try:
                self.ser.write(b"STOP\n")
            except Exception:
                pass

        self.close_serial()

        super().destroy_node()


# =============================================================
# MAIN
# =============================================================

def main(args=None):

    rclpy.init(args=args)

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