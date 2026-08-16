#!/usr/bin/env python3

import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


class DeliveryMission(Node):

    def __init__(self):
        super().__init__('delivery_mission')

        # =====================================================
        # SAVED MAP LOCATIONS
        # =====================================================

        self.home = {
            'x': -1.23230,
            'y': -1.86195,
            'yaw': 2.32865,
        }

        self.pickup_a = {
            'x': -1.56899,
            'y': -1.10715,
            'yaw': 0.70110,
        }

        self.nav_to_pose = ActionClient(
            self,
            NavigateToPose,
            '/navigate_to_pose'
        )

        self.get_logger().info('Delivery Mission Node started.')

    # =========================================================
    # CREATE NAV2 GOAL
    # =========================================================

    def make_goal(self, location):
        goal = NavigateToPose.Goal()

        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()

        pose.pose.position.x = location['x']
        pose.pose.position.y = location['y']
        pose.pose.position.z = 0.0

        yaw = location['yaw']

        pose.pose.orientation.x = 0.0
        pose.pose.orientation.y = 0.0
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)

        goal.pose = pose

        return goal

    # =========================================================
    # SEND ONE GOAL AND WAIT FOR RESULT
    # =========================================================

    def go_to(self, name, location):
        self.get_logger().info(
            f'Navigating to {name}: '
            f'x={location["x"]:.3f}, '
            f'y={location["y"]:.3f}, '
            f'yaw={location["yaw"]:.3f}'
        )

        if not self.nav_to_pose.wait_for_server(timeout_sec=5.0):
            self.get_logger().error(
                'Nav2 NavigateToPose action server is not available.'
            )
            return False

        goal = self.make_goal(location)

        send_future = self.nav_to_pose.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)

        goal_handle = send_future.result()

        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error(
                f'Nav2 rejected the goal for {name}.'
            )
            return False

        self.get_logger().info(
            f'Goal accepted for {name}. Waiting for arrival...'
        )

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result()

        if result is None:
            self.get_logger().error(
                f'No result received for {name}.'
            )
            return False

        if result.status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(
                f'Arrived successfully at {name}.'
            )
            return True

        self.get_logger().error(
            f'Navigation to {name} failed. '
            f'Nav2 status={result.status}'
        )
        return False

    # =========================================================
    # MISSION A: HOME -> PICKUP A -> HOME
    # =========================================================

    def run_mission(self):
        self.get_logger().info(
            'Starting Mission A: HOME -> PICKUP A -> HOME'
        )

        if not self.go_to('PICKUP A', self.pickup_a):
            self.get_logger().error(
                'Mission stopped: could not reach PICKUP A.'
            )
            return

        self.get_logger().info(
            'PICKUP A reached. Simulating pickup/loading step.'
        )

        # Later this can be replaced with a real pickup mechanism.

        if not self.go_to('HOME', self.home):
            self.get_logger().error(
                'Mission stopped: could not return HOME.'
            )
            return

        self.get_logger().info(
            'MISSION A COMPLETE: HOME -> PICKUP A -> HOME'
        )


def main(args=None):
    rclpy.init(args=args)

    node = DeliveryMission()

    try:
        node.run_mission()
    except KeyboardInterrupt:
        node.get_logger().info('Mission interrupted by user.')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
