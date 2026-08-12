#!/usr/bin/env python3

import math

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import LaserScan, Range
from geometry_msgs.msg import Twist


class SafetyNode(Node):

    def __init__(self):

        super().__init__('safety_node')


        # =====================================================
        # PARAMETERS
        # =====================================================

        # LiDAR stop distance
        self.stop_distance = 0.20 


        # Ultrasonic stop distance
        self.ultrasonic_stop_distance = 0.15


        # LiDAR front angle
        self.front_angle = math.radians(25.0)


        # Ultrasonic sensor timeout
        self.ultrasonic_timeout = 0.5


        # =====================================================
        # STATE
        # =====================================================

        self.latest_cmd = Twist()


        # LiDAR obstacle
        self.obstacle_front = False


        # Ultrasonic obstacle
        self.ultrasonic_obstacle = False


        # Latest ultrasonic reading
        self.ultrasonic_distance = float('nan')


        # Time of last ultrasonic message
        self.last_ultrasonic_time = (
            self.get_clock().now()
        )


        # Warning state
        self.last_warning_state = False


        # =====================================================
        # ROS SUBSCRIPTIONS
        # =====================================================

        # -----------------------------------------------------
        # LiDAR
        # -----------------------------------------------------

        self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )


        # -----------------------------------------------------
        # Ultrasonic
        # -----------------------------------------------------

        self.create_subscription(
            Range,
            '/ultrasonic',
            self.ultrasonic_callback,
            10
        )


        # -----------------------------------------------------
        # Original cmd_vel
        # -----------------------------------------------------

        self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_callback,
            10
        )


        # =====================================================
        # SAFE COMMAND PUBLISHER
        # =====================================================

        self.safe_cmd_pub = self.create_publisher(
            Twist,
            '/safe_cmd_vel',
            10
        )


        # =====================================================
        # TIMER
        # =====================================================

        self.timer = self.create_timer(
            0.05,
            self.publish_safe_command
        )


        # =====================================================
        # LOGGING
        # =====================================================

        self.get_logger().info(
            "Safety Node Started"
        )


        self.get_logger().info(
            f"LiDAR stop distance: "
            f"{self.stop_distance:.2f} m"
        )


        self.get_logger().info(
            f"Ultrasonic stop distance: "
            f"{self.ultrasonic_stop_distance:.2f} m"
        )


    # =========================================================
    # CMD CALLBACK
    # =========================================================

    def cmd_callback(self, msg):

        self.latest_cmd = msg


    # =========================================================
    # LIDAR CALLBACK
    # =========================================================

    def scan_callback(self, scan):

        valid_front_ranges = []


        for i, distance in enumerate(
            scan.ranges
        ):

            angle = (
                scan.angle_min +
                i * scan.angle_increment
            )


            # Normalize angle to [-pi, pi]

            angle = math.atan2(
                math.sin(angle),
                math.cos(angle)
            )


            # Only front +/-25 degrees

            if abs(angle) > self.front_angle:

                continue


            # Invalid values

            if not math.isfinite(
                distance
            ):

                continue


            if distance <= scan.range_min:

                continue


            if distance >= scan.range_max:

                continue


            valid_front_ranges.append(
                distance
            )


        # =====================================================
        # LIDAR OBSTACLE
        # =====================================================

        if valid_front_ranges:

            minimum_distance = min(
                valid_front_ranges
            )


            self.obstacle_front = (
                minimum_distance <
                self.stop_distance
            )


        else:

            self.obstacle_front = False


    # =========================================================
    # ULTRASONIC CALLBACK
    # =========================================================

    def ultrasonic_callback(self, msg):

        self.last_ultrasonic_time = (
            self.get_clock().now()
        )


        self.ultrasonic_distance = (
            msg.range
        )


        # -----------------------------------------------------
        # Invalid ultrasonic reading
        # -----------------------------------------------------

        if not math.isfinite(
            msg.range
        ):

            self.ultrasonic_obstacle = False

            return


        # -----------------------------------------------------
        # Obstacle check
        # -----------------------------------------------------

        self.ultrasonic_obstacle = (
            msg.range <
            self.ultrasonic_stop_distance
        )


        # -----------------------------------------------------
        # Warning
        # -----------------------------------------------------

        if (
            self.ultrasonic_obstacle
            and msg.range < self.ultrasonic_stop_distance
        ):
            self.get_logger().warn(
                f"EMERGENCY ULTRASONIC STOP: "
                f"{msg.range:.2f} m"
            )


    # =========================================================
    # SAFE COMMAND
    # =========================================================

    def publish_safe_command(self):

        cmd = Twist()


        # Copy latest command

        cmd.linear.x = (
            self.latest_cmd.linear.x
        )

        cmd.linear.y = (
            self.latest_cmd.linear.y
        )

        cmd.linear.z = (
            self.latest_cmd.linear.z
        )

        cmd.angular.x = (
            self.latest_cmd.angular.x
        )

        cmd.angular.y = (
            self.latest_cmd.angular.y
        )

        cmd.angular.z = (
            self.latest_cmd.angular.z
        )


        # =====================================================
        # ULTRASONIC TIMEOUT
        # =====================================================

        now = self.get_clock().now()


        ultrasonic_age = (
            (
                now -
                self.last_ultrasonic_time
            ).nanoseconds /
            1e9
        )


        ultrasonic_available = (
            ultrasonic_age <=
            self.ultrasonic_timeout
        )


        # =====================================================
        # COMBINED OBSTACLE
        # =====================================================

        obstacle_detected = (
            self.obstacle_front or
            (
                ultrasonic_available and
                self.ultrasonic_obstacle
            )
        )


        # =====================================================
        # BLOCK FORWARD MOTION
        # =====================================================

        if (
            obstacle_detected and
            cmd.linear.x > 0.0
        ):

            cmd.linear.x = 0.0


            # Keep angular.z available.
            #
            # This means the robot can turn away
            # from the obstacle.

            if not self.last_warning_state:

                if self.obstacle_front:

                    self.get_logger().warn(
                        "LiDAR obstacle ahead - "
                        "forward motion blocked"
                    )


                elif self.ultrasonic_obstacle:

                    self.get_logger().warn(
                        "LOW OBSTACLE ahead - "
                        "forward motion blocked"
                    )


            self.last_warning_state = True


        else:

            if self.last_warning_state:

                self.get_logger().info(
                    "Path clear - "
                    "forward motion available"
                )


            self.last_warning_state = False


        # =====================================================
        # PUBLISH
        # =====================================================

        self.safe_cmd_pub.publish(
            cmd
        )


# =============================================================
# MAIN
# =============================================================

def main(args=None):

    rclpy.init(
        args=args
    )


    node = SafetyNode()


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