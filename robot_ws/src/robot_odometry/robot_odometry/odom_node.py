#!/usr/bin/env python3

import math

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from std_msgs.msg import Int64MultiArray

import tf_transformations


class EncoderOdomNode(Node):

    def __init__(self):

        super().__init__('odom_node')


        # =====================================================
        # ROBOT PARAMETERS
        # =====================================================

        # User measurements:
        #
        # Wheel diameter = 6 cm
        # Wheel separation = 12.5 cm
        # Encoder = approximately 22 ticks/revolution

        self.WHEEL_DIAMETER = 0.060
        self.WHEEL_SEPARATION = 0.181
        self.TICKS_PER_REV = 22.0


        self.WHEEL_CIRCUMFERENCE = (
            math.pi *
            self.WHEEL_DIAMETER
        )

        self.DISTANCE_PER_TICK = (
            self.WHEEL_CIRCUMFERENCE /
            self.TICKS_PER_REV
        )


        # =====================================================
        # POSE
        # =====================================================

        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0


        # =====================================================
        # PREVIOUS ENCODER STATE
        # =====================================================

        self.previous_left = None
        self.previous_right = None

        self.previous_time = None


        # =====================================================
        # ROS
        # =====================================================

        self.encoder_sub = self.create_subscription(
            Int64MultiArray,
            '/wheel_ticks',
            self.encoder_callback,
            20
        )


        self.odom_pub = self.create_publisher(
            Odometry,
            '/wheel/odom',
            20
        )


        self.get_logger().info(
            "========================================"
        )

        self.get_logger().info(
            "ENCODER ODOMETRY STARTED"
        )

        self.get_logger().info(
            f"Wheel diameter: "
            f"{self.WHEEL_DIAMETER:.3f} m"
        )

        self.get_logger().info(
            f"Wheel separation: "
            f"{self.WHEEL_SEPARATION:.3f} m"
        )

        self.get_logger().info(
            f"Ticks/revolution: "
            f"{self.TICKS_PER_REV:.1f}"
        )

        self.get_logger().info(
            f"Distance/tick: "
            f"{self.DISTANCE_PER_TICK:.6f} m"
        )

        self.get_logger().info(
            "Publishing: /wheel/odom"
        )

        self.get_logger().info(
            "========================================"
        )


    # =========================================================
    # ENCODER CALLBACK
    # =========================================================

    def encoder_callback(self, msg):

        if len(msg.data) < 2:
            return


        left_ticks = int(msg.data[0])
        right_ticks = int(msg.data[1])


        now = self.get_clock().now()


        # First encoder message establishes baseline

        if (
            self.previous_left is None or
            self.previous_right is None or
            self.previous_time is None
        ):

            self.previous_left = left_ticks
            self.previous_right = right_ticks
            self.previous_time = now

            return


        # -----------------------------------------------------
        # Time
        # -----------------------------------------------------

        dt = (
            now -
            self.previous_time
        ).nanoseconds / 1e9


        if dt <= 0.0:

            self.previous_time = now

            return


        # -----------------------------------------------------
        # Tick difference
        # -----------------------------------------------------

        delta_left_ticks = (
            left_ticks -
            self.previous_left
        )

        delta_right_ticks = (
            right_ticks -
            self.previous_right
        )


        self.previous_left = left_ticks
        self.previous_right = right_ticks
        self.previous_time = now


        # -----------------------------------------------------
        # Convert ticks -> metres
        # -----------------------------------------------------

        left_distance = (
            delta_left_ticks *
            self.DISTANCE_PER_TICK
        )

        right_distance = (
            delta_right_ticks *
            self.DISTANCE_PER_TICK
        )


        # -----------------------------------------------------
        # Differential-drive odometry
        # -----------------------------------------------------

        delta_distance = (
            left_distance +
            right_distance
        ) / 2.0


        delta_theta = (
            right_distance -
            left_distance
        ) / self.WHEEL_SEPARATION


        # Midpoint integration improves turning accuracy

        heading_mid = (
            self.theta +
            delta_theta / 2.0
        )


        delta_x = (
            delta_distance *
            math.cos(heading_mid)
        )

        delta_y = (
            delta_distance *
            math.sin(heading_mid)
        )


        self.x += delta_x
        self.y += delta_y
        self.theta += delta_theta


        # Keep theta between -pi and +pi

        self.theta = math.atan2(
            math.sin(self.theta),
            math.cos(self.theta)
        )


        # -----------------------------------------------------
        # Velocity
        # -----------------------------------------------------

        linear_velocity = (
            delta_distance /
            dt
        )

        angular_velocity = (
            delta_theta /
            dt
        )


        self.publish_odometry(
            now,
            linear_velocity,
            angular_velocity
        )


    # =========================================================
    # PUBLISH ODOMETRY
    # =========================================================

    def publish_odometry(
        self,
        now,
        linear_velocity,
        angular_velocity
    ):

        q = tf_transformations.quaternion_from_euler(
            0.0,
            0.0,
            self.theta
        )


        odom = Odometry()


        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        odom.header.stamp = now.to_msg()

        odom.header.frame_id = "odom"

        odom.child_frame_id = "base_link"


        # -----------------------------------------------------
        # Pose
        # -----------------------------------------------------

        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0


        odom.pose.pose.orientation.x = float(q[0])
        odom.pose.pose.orientation.y = float(q[1])
        odom.pose.pose.orientation.z = float(q[2])
        odom.pose.pose.orientation.w = float(q[3])


        # Encoder resolution is fairly low (~22 ticks/rev),
        # therefore don't claim unrealistically tiny covariance.

        pose_covariance = [0.0] * 36

        pose_covariance[0] = 0.03
        pose_covariance[7] = 0.03

        # Z unused
        pose_covariance[14] = 99999.0

        # Roll/pitch unused
        pose_covariance[21] = 99999.0
        pose_covariance[28] = 99999.0

        pose_covariance[35] = 0.08


        odom.pose.covariance = pose_covariance


        # -----------------------------------------------------
        # Twist
        # -----------------------------------------------------

        odom.twist.twist.linear.x = (
            linear_velocity
        )

        odom.twist.twist.linear.y = 0.0

        odom.twist.twist.angular.z = (
            angular_velocity
        )


        twist_covariance = [0.0] * 36

        twist_covariance[0] = 0.03

        twist_covariance[7] = 0.10

        twist_covariance[14] = 99999.0
        twist_covariance[21] = 99999.0
        twist_covariance[28] = 99999.0

        twist_covariance[35] = 0.08


        odom.twist.covariance = twist_covariance


        self.odom_pub.publish(odom)


# =============================================================
# MAIN
# =============================================================

def main(args=None):

    rclpy.init(args=args)

    node = EncoderOdomNode()

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