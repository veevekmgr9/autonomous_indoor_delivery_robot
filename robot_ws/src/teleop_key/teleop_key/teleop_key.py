#!/usr/bin/env python3

import sys
import tty
import termios
import select
import threading

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import String


class WasdTeleop(Node):

    def __init__(self):
        super().__init__("teleop_key")

        self.cmd_pub = self.create_publisher(
            Twist,
            "/cmd_vel",
            10
        )

        self.motion_pub = self.create_publisher(
            String,
            "/motion_state",
            10
        )

        self.linear_speed = 0.20
        self.angular_speed = 0.80

        self.current_cmd = "S"
        self.running = True

        # Publish continuously (same behaviour as teleop_twist_keyboard)
        self.timer = self.create_timer(0.5, self.publish_command)

        self.get_logger().info("")
        self.get_logger().info("====== WASDX TELEOP ======")
        self.get_logger().info("W : Forward")
        self.get_logger().info("X : Backward")
        self.get_logger().info("A : Left")
        self.get_logger().info("D : Right")
        self.get_logger().info("S : Stop")
        self.get_logger().info("Q : Quit")
        self.get_logger().info("==========================")

        self.keyboard_thread = threading.Thread(target=self.keyboard_loop)
        self.keyboard_thread.daemon = True
        self.keyboard_thread.start()

    def get_key(self):

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)

            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)

            if rlist:
                key = sys.stdin.read(1)
            else:
                key = ""

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        return key.lower()

    def publish_command(self):

        twist = Twist()

        if self.current_cmd == "F":
            twist.linear.x = self.linear_speed
            twist.angular.z = 0.0

        elif self.current_cmd == "B":
            twist.linear.x = -self.linear_speed
            twist.angular.z = 0.0

        elif self.current_cmd == "L":
            twist.linear.x = 0.0
            twist.angular.z = self.angular_speed

        elif self.current_cmd == "R":
            twist.linear.x = 0.0
            twist.angular.z = -self.angular_speed

        else:
            twist.linear.x = 0.0
            twist.angular.z = 0.0

        motion = String()
        motion.data = self.current_cmd

        self.cmd_pub.publish(twist)
        self.motion_pub.publish(motion)

    def keyboard_loop(self):

        while self.running and rclpy.ok():

            key = self.get_key()

            if key == "":
                continue

            elif key == "w":
                self.current_cmd = "F"
                self.get_logger().info("Forward")

            elif key == "x":
                self.current_cmd = "B"
                self.get_logger().info("Backward")

            elif key == "a":
                self.current_cmd = "L"
                self.get_logger().info("Left")

            elif key == "d":
                self.current_cmd = "R"
                self.get_logger().info("Right")

            elif key == "s":
                self.current_cmd = "S"
                self.get_logger().info("Stop")

            elif key == "q":
                self.running = False
                rclpy.shutdown()
                break


def main():

    rclpy.init()

    node = WasdTeleop()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.running = False
    node.destroy_node()

    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()