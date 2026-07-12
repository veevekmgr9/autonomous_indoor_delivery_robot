import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from nav_msgs.msg import Odometry

import tf_transformations
import tf2_ros
from geometry_msgs.msg import TransformStamped

import math

class OdomNode(Node):

    def __init__(self):
        super().__init__('odom_node')

        # ---- STATE ----
        self.x = 0.0
        self.y = 0.0
        self.th = 0.0

        self.v = 0.15     # forward speed estimate
        self.w = 0.6      # turn speed estimate

        self.last_time = self.get_clock().now()

        # ---- SUB ----
        self.create_subscription(
            String,
            '/motion_state',
            self.motion_callback,
            10
        )

        # ---- PUB ----
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)

        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        self.last_cmd = "S"

        self.timer = self.create_timer(0.1, self.update)

        self.get_logger().info("Odometry Node Started ✔")

    def motion_callback(self, msg):
        cmd = msg.data.upper()

        if cmd in ["FORWARD", "F"]:
            self.last_cmd = "F"
        elif cmd in ["BACKWARD", "B"]:
            self.last_cmd = "B"
        elif cmd in ["LEFT", "L"]:
            self.last_cmd = "L"
        elif cmd in ["RIGHT", "R"]:
            self.last_cmd = "R"
        else:
            self.last_cmd = "S"

    def update(self):

        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        self.last_time = now

        cmd = self.last_cmd

        dx = 0.0
        dy = 0.0
        dth = 0.0

        if cmd == "F":
            dx = self.v * dt
        elif cmd == "B":
            dx = -self.v * dt
        elif cmd == "L":
            dth = self.w * dt
        elif cmd == "R":
            dth = -self.w * dt

        # ---- UPDATE POSE ----
        self.th += dth

        self.x += dx * math.cos(self.th)
        self.y += dx * math.sin(self.th)

        # ---- QUATERNION ----
        q = tf_transformations.quaternion_from_euler(0, 0, self.th)

        # ---- ODOM MESSAGE ----
        odom = Odometry()

        odom.header.stamp = now.to_msg()
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_footprint"

        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y

        odom.pose.pose.orientation.x = q[0]
        odom.pose.pose.orientation.y = q[1]
        odom.pose.pose.orientation.z = q[2]
        odom.pose.pose.orientation.w = q[3]

        self.odom_pub.publish(odom)

        # ---- TF ----
        t = TransformStamped()
        t.header.stamp = now.to_msg()
        t.header.frame_id = "odom"
        t.child_frame_id = "base_footprint"

        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0

        t.transform.rotation.x = q[0]
        t.transform.rotation.y = q[1]
        t.transform.rotation.z = q[2]
        t.transform.rotation.w = q[3]

        self.tf_broadcaster.sendTransform(t)


def main():
    rclpy.init()
    node = OdomNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()