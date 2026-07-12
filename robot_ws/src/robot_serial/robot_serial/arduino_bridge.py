import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import String
from sensor_msgs.msg import Imu

import serial
import time
import math
import subprocess
import glob


class ArduinoBridge(Node):

    def __init__(self):
        super().__init__('arduino_bridge')

        # ---------------- SERIAL CONFIG ----------------
        self.serial_port = '/dev/ttyACM0'
        self.baud_rate = 115200

        # Differential-drive mixing params (tune these for your robot)
        self.max_pwm_speed = 150.0   # matches motorSpeed in firmware
        self.linear_scale = 1.0      # scales msg.linear.x  -> PWM units
        self.angular_scale = 1.0     # scales msg.angular.z -> PWM units

        # IMU watchdog: if no valid IMU line arrives within this window,
        # assume the Arduino reset/reconnected and force a full re-open
        # (not just a bare START) since a soft resend can't recover a
        # genuinely stuck MCU/USB-CDC state.
        self.imu_timeout_sec = 2.0
        self.last_imu_time = time.time()

        self.synced = False
        self.ser = None

        self.open_serial()

        # ---------------- ROS ----------------
        self.imu_pub = self.create_publisher(Imu, '/imu/data_raw', 10)
        self.motion_pub = self.create_publisher(String, '/motion_state', 10)

        self.create_subscription(Twist, '/safe_cmd_vel', self.cmd_callback, 10)

        # Fast serial poll - must stay non-blocking (see read_serial)
        self.timer = self.create_timer(0.02, self.read_serial)

        # Slower watchdog to catch silent disconnects/resets
        self.watchdog_timer = self.create_timer(0.5, self.check_imu_watchdog)

        self.get_logger().info("Arduino Bridge Started (STABLE MODE)")

    # =========================================================
    # SERIAL CONNECTION HANDLING
    # =========================================================
    def open_serial(self):
        self.reset_usb_device()
        try:
            if self.ser is not None:
                try:
                    self.ser.close()
                except Exception:
                    pass

            self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=0.2)

            # Explicitly force a low -> high DTR edge to guarantee a
            # hardware reset pulse, no matter what state DTR was left
            # in by whatever last touched this port.
            self.ser.dtr = False
            time.sleep(0.1)
            self.ser.dtr = True

            self.get_logger().info("Arduino port opened, forced hardware reset")

            # Wait for the boot banner instead of blindly sleeping -
            # more robust than a fixed delay and lets us detect a
            # truly dead board quickly.
            if not self._wait_for_line("READY", timeout=5.0):
                self.get_logger().warn("Did not see READY after reset - board may be unresponsive")

            time.sleep(1)

            self.get_logger().info("Sending START to trigger MPU6050 reset...")
            self.ser.write(b"START\n")

            mpu_confirmed = self._wait_for_line("MPU_RESET_COMPLETE", timeout=1.0)

            if mpu_confirmed:
                self.get_logger().info("MPU6050 reset successful! Resuming IMU topic stream.")
                self.synced = True
            else:
                self.get_logger().warn("MPU confirmation flag missing, attempting sync anyway.")
                self.synced = False

            self.last_imu_time = time.time()

        except Exception as e:
            self.get_logger().error(f"Serial connection failed: {e}")
            self.ser = None
    
    def reset_usb_device(self):

        try:
            vid = "04d9"
            pid = "b534"

            devices = glob.glob(
                f"/sys/bus/usb/devices/*/idVendor"
            )

            usb_device = None

            for dev in devices:
                try:
                    with open(dev, "r") as f:
                        device_vid = f.read().strip()

                    with open(dev.replace("idVendor", "idProduct"), "r") as f:
                        device_pid = f.read().strip()

                    if device_vid == vid and device_pid == pid:
                        usb_device = dev.replace("/idVendor", "")
                        break

                except:
                    pass


            if usb_device is None:
                self.get_logger().warn(
                    "Arduino USB device not found"
                )
                return


            device_name = usb_device.split("/")[-1]

            self.get_logger().info(
                f"USB reset: {device_name}"
            )


            # Disconnect USB device
            subprocess.run(
                ["sudo", "sh", "-c",
                f"echo {device_name} > /sys/bus/usb/drivers/usb/unbind"]
            )


            time.sleep(2)


            # Reconnect USB device
            subprocess.run(
                ["sudo", "sh", "-c",
                f"echo {device_name} > /sys/bus/usb/drivers/usb/bind"]
            )


            time.sleep(3)

            self.get_logger().info(
                "USB reset completed"
            )


        except Exception as e:
            self.get_logger().error(
                f"USB reset failed: {e}"
            )

    def _wait_for_line(self, expected_substr, timeout):
        """Blocks briefly (used only during connect/reconnect, never
        in the main timer loop) waiting for a specific line from the
        Arduino."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if expected_substr in line:
                    return True
            else:
                time.sleep(0.01)
        return False

    def check_imu_watchdog(self):
        """
        If we haven't seen a valid IMU packet in a while, don't just
        resend START - that only helps if the MCU is alive and simply
        forgot rosConnected. If it's actually wedged (stuck I2C,
        stuck USB-CDC TX), only a full hardware reset via open_serial()
        recovers it, same as your manual baud-toggle fix.
        """
        if self.ser is None:
            self.get_logger().warn("Serial port not open, attempting reconnect...")
            self.open_serial()
            return

        if time.time() - self.last_imu_time > self.imu_timeout_sec:
            self.get_logger().warn("No IMU data recently, forcing full reconnect + hardware reset")
            self.open_serial()

    # =========================================================
    # CMD -> Arduino
    # =========================================================
    def cmd_callback(self, msg):
        x = msg.linear.x
        z = msg.angular.z

        left = (x * self.linear_scale) - (z * self.angular_scale)
        right = (x * self.linear_scale) + (z * self.angular_scale)

        cmd = "S"

        if abs(left) < 1e-3 and abs(right) < 1e-3:
            cmd = "S"
        elif left > 0 and right > 0:
            cmd = "W"
        elif left < 0 and right < 0:
            cmd = "X"
        elif left < right:
            cmd = "A"
        elif right < left:
            cmd = "D"

        if self.ser is None:
            return

        try:
            self.ser.write((cmd + "\n").encode())
        except Exception as e:
            self.get_logger().error(f"Write failed, reopening port: {e}")
            self.open_serial()

    # =========================================================
    # SERIAL READER (non-blocking)
    # =========================================================
    def read_serial(self):
        if self.ser is None:
            return

        try:
            # Don't block the executor waiting for a newline that may
            # never come - only read if data is actually available.
            if self.ser.in_waiting == 0:
                return

            raw = self.ser.readline().decode('utf-8', errors='ignore').strip()

            if not raw:
                return

            # ---------------- RESYNC MODE ----------------
            if not self.synced:
                if raw.startswith("$IMU") and raw.endswith("*"):
                    parts = raw.replace("$IMU,", "").replace("*", "").split(",")
                    if len(parts) == 6:
                        self.synced = True
                        self.get_logger().info("IMU SYNCED AFTER RESTART")
                    else:
                        return
                else:
                    return

            # ---------------- NORMAL STREAM ----------------
            if not (raw.startswith("$IMU") and raw.endswith("*")):
                return

            data = raw.replace("$IMU,", "").replace("*", "")
            parts = data.split(",")

            if len(parts) != 6:
                self.synced = False  # force resync again
                return

            ax, ay, az, gx, gy, gz = map(float, parts)

            imu = Imu()
            imu.header.stamp = self.get_clock().now().to_msg()
            imu.header.frame_id = "imu_link"

            g = 9.80665

            imu.linear_acceleration.x = (ax / 16384.0) * g
            imu.linear_acceleration.y = (ay / 16384.0) * g
            imu.linear_acceleration.z = (az / 16384.0) * g

            imu.angular_velocity.x = (gx / 131.0) * (math.pi / 180.0)
            imu.angular_velocity.y = (gy / 131.0) * (math.pi / 180.0)
            imu.angular_velocity.z = (gz / 131.0) * (math.pi / 180.0)

            imu.orientation_covariance[0] = -1

            # EKF SAFE COVARIANCE
            imu.linear_acceleration_covariance = [
                0.2, 0, 0,
                0, 0.2, 0,
                0, 0, 0.2
            ]

            imu.angular_velocity_covariance = [
                0.05, 0, 0,
                0, 0.05, 0,
                0, 0, 0.05
            ]

            self.imu_pub.publish(imu)
            self.last_imu_time = time.time()

            self.get_logger().debug(
                f"IMU Data Published: ax={ax:.2f}, ay={ay:.2f}, az={az:.2f}, "
                f"gx={gx:.2f}, gy={gy:.2f}, gz={gz:.2f}"
            )

        except Exception as e:
            self.get_logger().error(f"Serial error: {e}")

    def destroy_node(self):
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
        super().destroy_node()


# =========================================================
def main():
    rclpy.init()
    node = ArduinoBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()