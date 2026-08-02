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

        self.LINEAR_CALIBRATION = 10
        self.ANGULAR_CALIBRATION = 10

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
            0.02,
            self.update
        )
        self.get_logger().info("Calibrated Odometry Node Started ✔")

        self.get_logger().info(
            "Odometry using /safe_cmd_vel started ✔"
        )



    def cmd_callback(self,msg):

        # Take real commanded velocity

        self.v = msg.linear.x * self.LINEAR_CALIBRATION
        self.w = msg.angular.z * self.ANGULAR_CALIBRATION



    def update(self):

        now = self.get_clock().now()


        dt = (
            now - self.last_time
        ).nanoseconds / 1e9


        self.last_time = now

        if dt > 0.1 or dt <= 0.0:
            return

        # -----------------
        # Differential drive model
        # -----------------

        # self.th += self.w * dt
        delta_theta = self.w * dt

        delta_x = self.v * math.cos(self.th + delta_theta / 2.0) * dt
        delta_y = self.v * math.sin(self.th + delta_theta / 2.0) * dt

        self.x += delta_x
        self.y += delta_y
        self.th += delta_theta


        # self.x += (
        #     self.v *
        #     math.cos(self.th) *
        #     dt
        # )


        # self.y += (
        #     self.v *
        #     math.sin(self.th) *
        #     dt
        # )



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
        odom.pose.pose.position.z = 0.0


        odom.pose.pose.orientation.x = float(q[0])

        odom.pose.pose.orientation.y = float(q[1])

        odom.pose.pose.orientation.z = float(q[2])

        odom.pose.pose.orientation.w = float(q[3])

        # Pose covariance
        pose_cov = [0.0] * 36
        pose_cov[0] = 0.05
        pose_cov[7] = 0.05
        pose_cov[35] = 0.10
        odom.pose.covariance = pose_cov
        # odom.pose.covariance = [0.0] * 36
        # odom.pose.covariance[0] = 0.05      # x
        # odom.pose.covariance[7] = 0.05      # y
        # odom.pose.covariance[35] = 0.10     # yaw

        # Twist covariance
        twist_cov = [0.0] * 36
        twist_cov[0] = 0.02
        twist_cov[7] = 0.02
        twist_cov[35] = 0.05
        odom.twist.covariance = twist_cov
        # odom.twist.covariance = [0.0] * 36
        # odom.twist.covariance[0] = 0.02
        # odom.twist.covariance[7] = 0.02
        # odom.twist.covariance[35] = 0.05



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



        t.transform.rotation.x = float(q[0])

        t.transform.rotation.y = float(q[1])

        t.transform.rotation.z = float(q[2])

        t.transform.rotation.w = float(q[3])


        self.tf_broadcaster.sendTransform(t)



def main():

    rclpy.init()

    node = OdomNode()

    rclpy.spin(node)


    node.destroy_node()

    rclpy.shutdown()



if __name__ == '__main__':
    main()