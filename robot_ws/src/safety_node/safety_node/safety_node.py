#!/usr/bin/env python3

import math

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist


class SafetyNode(Node):

    def __init__(self):

        super().__init__('safety_node')


        # =====================================================
        # PARAMETERS
        # =====================================================

        self.stop_distance = 0.35

        # Check +/- 25 degrees in front
        self.front_angle = math.radians(25.0)

        self.latest_cmd = Twist()

        self.obstacle_front = False

        self.last_warning_state = False


        # =====================================================
        # ROS
        # =====================================================

        self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )


        self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_callback,
            10
        )


        self.safe_cmd_pub = self.create_publisher(
            Twist,
            '/safe_cmd_vel',
            10
        )


        # Publish continuously so Arduino gets regular commands

        self.timer = self.create_timer(
            0.05,
            self.publish_safe_command
        )


        self.get_logger().info(
            "Safety Node Started"
        )

        self.get_logger().info(
            f"Forward stop distance: "
            f"{self.stop_distance:.2f} m"
        )


    # =========================================================
    # CMD CALLBACK
    # =========================================================

    def cmd_callback(self, msg):

        self.latest_cmd = msg


    # =========================================================
    # LIDAR
    # =========================================================

    def scan_callback(self, scan):

        valid_front_ranges = []


        for i, distance in enumerate(scan.ranges):

            angle = (
                scan.angle_min +
                i * scan.angle_increment
            )


            # Normalize angle into [-pi, pi]

            angle = math.atan2(
                math.sin(angle),
                math.cos(angle)
            )


            if abs(angle) > self.front_angle:
                continue


            if not math.isfinite(distance):
                continue


            if distance <= scan.range_min:
                continue


            if distance >= scan.range_max:
                continue


            valid_front_ranges.append(
                distance
            )


        if valid_front_ranges:

            minimum_distance = min(
                valid_front_ranges
            )

            self.obstacle_front = (
                minimum_distance <
                self.stop_distance
            )

        else:

            # No valid front measurements.
            # Do not trigger false emergency stop here.
            self.obstacle_front = False


        if (
            self.obstacle_front and
            not self.last_warning_state
        ):

            self.get_logger().warn(
                "Obstacle ahead - forward motion blocked"
            )


        elif (
            not self.obstacle_front and
            self.last_warning_state
        ):

            self.get_logger().info(
                "Path clear"
            )


        self.last_warning_state = (
            self.obstacle_front
        )


    # =========================================================
    # SAFE COMMAND
    # =========================================================

    def publish_safe_command(self):

        cmd = Twist()


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


        # Block forward translation only.
        #
        # Reverse and turning remain available.

        if (
            self.obstacle_front and
            cmd.linear.x > 0.0
        ):

            cmd.linear.x = 0.0


        self.safe_cmd_pub.publish(cmd)


# =============================================================
# MAIN
# =============================================================

def main(args=None):

    rclpy.init(args=args)

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
# import rclpy
# from rclpy.node import Node
# from sensor_msgs.msg import LaserScan
# from geometry_msgs.msg import Twist
# import math

# class SafetyNode(Node):

#     def __init__(self):
#         super().__init__('safety_node')

#         self.sub_scan = self.create_subscription(
#             LaserScan,
#             '/scan',
#             self.scan_callback,
#             10
#         )

#         self.sub_cmd = self.create_subscription(
#             Twist,
#             '/cmd_vel',
#             self.cmd_callback,
#             10
#         )

#         self.pub_cmd = self.create_publisher(
#             Twist,
#             '/safe_cmd_vel',
#             10
#         )

#         self.latest_cmd = Twist()
#         self.get_logger().info("Safety Monitoring Node Started 🛑")

#     def cmd_callback(self, msg):
#         self.latest_cmd = msg

#     def scan_callback(self, scan):
#         # Slice the front indices (adjust these slices based on your LiDAR's resolution)
#         mid_index = len(scan.ranges) // 2
#         front_ranges = scan.ranges[mid_index - 10 : mid_index + 10]

#         # Filter out invalid, inf, and nan values to prevent code crashes
#         valid_ranges = [r for r in front_ranges if math.isfinite(r) and r > scan.range_min]

#         # Check for obstacles only if valid data exists
#         if valid_ranges and min(valid_ranges) < 0.5:
#             self.get_logger().warn("Obstacle detected nearby! 🚨")

#         # Always pass through the original command without stopping
#         cmd = self.latest_cmd
#         self.pub_cmd.publish(cmd)

# def main():
#     rclpy.init()
#     node = SafetyNode()
#     rclpy.spin(node)
#     node.destroy_node()
#     rclpy.shutdown()

# if __name__ == '__main__':
#     main()


# import rclpy
# from rclpy.node import Node
# from sensor_msgs.msg import LaserScan
# from geometry_msgs.msg import Twist
# import math

# class SafetyNode(Node):

#     def __init__(self):
#         super().__init__('safety_node')

#         self.sub_scan = self.create_subscription(
#             LaserScan,
#             '/scan',
#             self.scan_callback,
#             10
#         )

#         self.sub_cmd = self.create_subscription(
#             Twist,
#             '/cmd_vel',
#             self.cmd_callback,
#             10
#         )

#         self.pub_cmd = self.create_publisher(
#             Twist,
#             '/safe_cmd_vel',
#             10
#         )

#         self.latest_cmd = Twist()
#         self.safe = True

#         self.get_logger().info("Safety Node Started 🛑")

#     def cmd_callback(self, msg):
#         self.latest_cmd = msg

#     import math

#     # def scan_callback(self, scan):
#     #     mid = len(scan.ranges) // 2
#     #     front_ranges = scan.ranges[mid - 5 : mid + 5]
#     #     # Filter out inf/nan
#     #     valid = [r for r in front_ranges if math.isfinite(r) and r > 0.0]
        
#     #     if not valid:
#     #         self.safe = True  # No valid readings, assume clear
#     #     elif min(valid) < 0.5:
#     #         self.safe = False

#     #     cmd = Twist()
#     #     if self.safe:
#     #         cmd = self.latest_cmd
#     #     else:
#     #         cmd.linear.x = 0.0
#     #         cmd.angular.z = 0.0
#     #         self.get_logger().warn("Obstacle detected! STOP 🚨")

#     #     self.pub_cmd.publish(cmd)

#     def scan_callback(self, scan):

#         # Check front 30 degrees
#         front_ranges = scan.ranges[len(scan.ranges)//2 - 10 : len(scan.ranges)//2 + 10]

#         min_distance = min(front_ranges)

#         if min_distance < 0.5:
#             self.safe = False
#         else:
#             self.safe = True

#         cmd = Twist()

#         if self.safe:
#             cmd = self.latest_cmd
#         else:
#             # cmd.linear.x = 0.0
#             # cmd.angular.z = 0.0
#             self.get_logger().warn("Obstacle detected! STOP 🚨")

#         self.pub_cmd.publish(cmd)

# def main():
#     rclpy.init()
#     node = SafetyNode()
#     rclpy.spin(node)
#     node.destroy_node()
#     rclpy.shutdown()

# if __name__ == '__main__':
#     main()