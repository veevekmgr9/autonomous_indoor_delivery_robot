import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, TransformStamped

import tf_transformations
import tf2_ros

import math


class OdomNode(Node):

    def __init__(self):

        super().__init__('odom_node')


        # -----------------
        # Robot pose
        # -----------------

        self.x = 0.0
        self.y = 0.0
        self.th = 0.0


        # current velocity
        self.v = 0.0
        self.w = 0.0


        self.last_time = self.get_clock().now()


        # -----------------
        # Subscribe
        # -----------------

        self.create_subscription(
            Twist,
            '/safe_cmd_vel',
            self.cmd_callback,
            10
        )


        # -----------------
        # Publisher
        # -----------------

        self.odom_pub = self.create_publisher(
            Odometry,
            '/odom',
            10
        )


        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)



        # update 10Hz
        self.timer = self.create_timer(
            0.1,
            self.update
        )


        self.get_logger().info(
            "Odometry using /safe_cmd_vel started ✔"
        )



    def cmd_callback(self,msg):

        # Take real commanded velocity

        self.v = msg.linear.x
        self.w = msg.angular.z



    def update(self):

        now = self.get_clock().now()


        dt = (
            now - self.last_time
        ).nanoseconds / 1e9


        self.last_time = now



        # -----------------
        # Differential drive model
        # -----------------

        self.th += self.w * dt


        self.x += (
            self.v *
            math.cos(self.th) *
            dt
        )


        self.y += (
            self.v *
            math.sin(self.th) *
            dt
        )



        # quaternion

        q = tf_transformations.quaternion_from_euler(
            0,
            0,
            self.th
        )



        # -----------------
        # ODOM message
        # -----------------

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



        # velocity information

        odom.twist.twist.linear.x = self.v

        odom.twist.twist.angular.z = self.w



        self.odom_pub.publish(odom)



        # -----------------
        # TF
        # -----------------

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