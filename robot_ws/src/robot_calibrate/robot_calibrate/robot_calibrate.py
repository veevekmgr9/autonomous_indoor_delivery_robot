import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time


class CalibrateRobot(Node):

    def __init__(self):
        super().__init__('calibrate_robot')
        self.pub = self.create_publisher(Twist, '/safe_cmd_vel', 10)
        time.sleep(1.0)  # wait for publisher to connect

    def send(self, vx=0.0, wz=0.0, duration=0.0):
        msg = Twist()
        msg.linear.x = vx
        msg.angular.z = wz

        end = time.time() + duration
        while time.time() < end:
            self.pub.publish(msg)
            time.sleep(0.05)

        # Stop
        stop = Twist()
        self.pub.publish(stop)
        time.sleep(0.5)

    def run(self):
        print("\n========================================")
        print("  Elegoo Smart Car Calibration")
        print("========================================")
        print("\nPlace robot on a flat surface.")
        print("Mark the START position with tape.")
        input("\nPress ENTER to drive FORWARD for 2 seconds...")

        self.send(vx=1.0, duration=2.0)  # vx=1.0 just triggers "W" command

        distance = input("\nMeasure distance from start to robot front (metres): ")
        try:
            d = float(distance)
            v = d / 2.0
            print(f"\n  ✔  Forward speed v = {v:.3f} m/s")
        except ValueError:
            v = 0.15
            print("  Invalid input, using default v=0.15")

        print("\n----------------------------------------")
        print("Now measuring ROTATION speed.")
        print("Place a marker on the robot front.")
        input("\nPress ENTER to SPIN LEFT for 3 seconds...")

        self.send(wz=1.0, duration=3.0)  # wz=1.0 triggers "A" command

        angle = input("\nHow many degrees did the robot rotate? (e.g. 270): ")
        try:
            import math
            a = float(angle) * math.pi / 180.0
            w = a / 3.0
            print(f"\n  ✔  Rotation speed w = {w:.3f} rad/s")
        except ValueError:
            w = 0.6
            print("  Invalid input, using default w=0.6")

        print("\n========================================")
        print("  CALIBRATION RESULT")
        print("========================================")
        print(f"\nUpdate these values in odom_node.py:\n")
        print(f"  self.v = {v:.3f}   # forward speed m/s")
        print(f"  self.w = {w:.3f}   # rotation speed rad/s")
        print("\n========================================\n")


def main():
    rclpy.init()
    node = CalibrateRobot()
    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()