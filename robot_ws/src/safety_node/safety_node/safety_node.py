import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
import math

class SafetyNode(Node):

    def __init__(self):
        super().__init__('safety_node')

        self.sub_scan = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )

        self.sub_cmd = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_callback,
            10
        )

        self.pub_cmd = self.create_publisher(
            Twist,
            '/safe_cmd_vel',
            10
        )

        self.latest_cmd = Twist()
        self.get_logger().info("Safety Monitoring Node Started 🛑")

    def cmd_callback(self, msg):
        self.latest_cmd = msg

    def scan_callback(self, scan):
        # Slice the front indices (adjust these slices based on your LiDAR's resolution)
        mid_index = len(scan.ranges) // 2
        front_ranges = scan.ranges[mid_index - 10 : mid_index + 10]

        # Filter out invalid, inf, and nan values to prevent code crashes
        valid_ranges = [r for r in front_ranges if math.isfinite(r) and r > scan.range_min]

        # Check for obstacles only if valid data exists
        if valid_ranges and min(valid_ranges) < 0.5:
            self.get_logger().warn("Obstacle detected nearby! 🚨")

        # Always pass through the original command without stopping
        cmd = self.latest_cmd
        self.pub_cmd.publish(cmd)

def main():
    rclpy.init()
    node = SafetyNode()
    rclpy.spin(node)
    node.destroy_node()
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