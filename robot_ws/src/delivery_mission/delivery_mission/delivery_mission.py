#!/usr/bin/env python3

import math
import time

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
            'x': -0.852895,
            'y': -2.22339,
            'yaw': 0.0
        }

        self.pickup_a = {
            'x': -1.56899,
            'y': -1.10715,
            'yaw': 0.70110
        }

        # =====================================================
        # NAVIGATION SETTINGS
        # =====================================================

        # Maximum time allowed for one navigation attempt
        self.navigation_timeout = 120.0

        # Number of attempts for each location
        self.max_retries = 3

        # Time to simulate pickup/loading
        self.pickup_wait_time = 3.0

        # =====================================================
        # NAV2 ACTION CLIENT
        # =====================================================

        self.nav_to_pose = ActionClient(
            self,
            NavigateToPose,
            '/navigate_to_pose'
        )

        self.get_logger().info(
            'Delivery Mission Node started.'
        )

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

        pose.pose.orientation.z = math.sin(
            yaw / 2.0
        )

        pose.pose.orientation.w = math.cos(
            yaw / 2.0
        )

        goal.pose = pose

        return goal

    # =========================================================
    # WAIT FOR NAV2
    # =========================================================

    def wait_for_nav2(self):

        self.get_logger().info(
            'Waiting for Nav2 NavigateToPose action server...'
        )

        available = self.nav_to_pose.wait_for_server(
            timeout_sec=15.0
        )

        if available:

            self.get_logger().info(
                'Nav2 NavigateToPose action server is ready.'
            )

        else:

            self.get_logger().error(
                'Nav2 NavigateToPose action server is NOT available.'
            )

        return available

    # =========================================================
    # SEND ONE NAVIGATION GOAL
    # =========================================================

    def go_to_once(self, name, location):

        self.get_logger().info(
            f'Navigating to {name}: '
            f'x={location["x"]:.3f}, '
            f'y={location["y"]:.3f}, '
            f'yaw={location["yaw"]:.3f}'
        )

        # -----------------------------------------------------
        # CREATE GOAL
        # -----------------------------------------------------

        goal = self.make_goal(location)

        # -----------------------------------------------------
        # SEND GOAL
        # -----------------------------------------------------

        send_future = self.nav_to_pose.send_goal_async(
            goal
        )

        rclpy.spin_until_future_complete(
            self,
            send_future
        )

        goal_handle = send_future.result()

        if goal_handle is None:

            self.get_logger().error(
                f'No goal handle received for {name}.'
            )

            return False

        if not goal_handle.accepted:

            self.get_logger().error(
                f'Nav2 rejected the goal for {name}.'
            )

            return False

        self.get_logger().info(
            f'Goal accepted for {name}.'
        )

        # -----------------------------------------------------
        # WAIT FOR RESULT
        # -----------------------------------------------------

        result_future = goal_handle.get_result_async()

        start_time = time.monotonic()

        while not result_future.done():

            rclpy.spin_once(
                self,
                timeout_sec=0.1
            )

            elapsed = (
                time.monotonic()
                - start_time
            )

            # -------------------------------------------------
            # NAVIGATION TIMEOUT
            # -------------------------------------------------

            if elapsed > self.navigation_timeout:

                self.get_logger().warn(
                    f'Navigation to {name} timed out '
                    f'after {self.navigation_timeout:.0f} seconds.'
                )

                cancel_future = (
                    goal_handle.cancel_goal_async()
                )

                rclpy.spin_until_future_complete(
                    self,
                    cancel_future,
                    timeout_sec=5.0
                )

                self.get_logger().warn(
                    f'Navigation attempt to {name} cancelled.'
                )

                return False

        # -----------------------------------------------------
        # GET RESULT
        # -----------------------------------------------------

        result = result_future.result()

        if result is None:

            self.get_logger().error(
                f'No result received for {name}.'
            )

            return False

        status = result.status

        # -----------------------------------------------------
        # SUCCESS
        # -----------------------------------------------------

        if status == GoalStatus.STATUS_SUCCEEDED:

            self.get_logger().info(
                f'✓ Arrived successfully at {name}.'
            )

            return True

        # -----------------------------------------------------
        # FAILURE
        # -----------------------------------------------------

        self.get_logger().error(
            f'Navigation to {name} failed. '
            f'Nav2 status={status}'
        )

        return False

    # =========================================================
    # SEND GOAL WITH RETRIES
    # =========================================================

    def go_to(self, name, location):

        for attempt in range(
            1,
            self.max_retries + 1
        ):

            self.get_logger().info(
                '----------------------------------------'
            )

            self.get_logger().info(
                f'{name}: navigation attempt '
                f'{attempt}/{self.max_retries}'
            )

            success = self.go_to_once(
                name,
                location
            )

            if success:

                return True

            # -------------------------------------------------
            # RETRY
            # -------------------------------------------------

            if attempt < self.max_retries:

                self.get_logger().warn(
                    f'{name} was not reached.'
                )

                self.get_logger().warn(
                    'Waiting before retrying...'
                )

                time.sleep(2.0)

        # -----------------------------------------------------
        # ALL ATTEMPTS FAILED
        # -----------------------------------------------------

        self.get_logger().error(
            f'Failed to reach {name} after '
            f'{self.max_retries} attempts.'
        )

        return False

    # =========================================================
    # PICKUP OPERATION
    # =========================================================

    def pickup_operation(self):

        self.get_logger().info(
            '----------------------------------------'
        )

        self.get_logger().info(
            'PICKUP A reached.'
        )

        self.get_logger().info(
            'Simulating package pickup/loading...'
        )

        time.sleep(
            self.pickup_wait_time
        )

        self.get_logger().info(
            'Pickup/loading completed.'
        )

    # =========================================================
    # MAIN DELIVERY MISSION
    # HOME -> PICKUP A -> HOME
    # =========================================================

    def run_mission(self):

        self.get_logger().info(
            '========================================'
        )

        self.get_logger().info(
            'STARTING DELIVERY MISSION'
        )

        self.get_logger().info(
            'HOME -> PICKUP A -> HOME'
        )

        self.get_logger().info(
            '========================================'
        )

        # =====================================================
        # WAIT FOR NAV2
        # =====================================================

        if not self.wait_for_nav2():

            self.get_logger().error(
                'Mission cannot start because Nav2 is unavailable.'
            )

            return

        # =====================================================
        # STEP 1
        # HOME -> PICKUP A
        # =====================================================

        self.get_logger().info(
            'STEP 1: HOME -> PICKUP A'
        )

        pickup_success = self.go_to(
            'PICKUP A',
            self.pickup_a
        )

        if not pickup_success:

            self.get_logger().error(
                'MISSION FAILED: Could not reach PICKUP A.'
            )

            return

        # =====================================================
        # STEP 2
        # PICKUP
        # =====================================================

        self.pickup_operation()

        # =====================================================
        # STEP 3
        # PICKUP A -> HOME
        # =====================================================

        self.get_logger().info(
            'STEP 2: PICKUP A -> HOME'
        )

        home_success = self.go_to(
            'HOME',
            self.home
        )

        if not home_success:

            self.get_logger().error(
                'MISSION FAILED: Could not return HOME.'
            )

            return

        # =====================================================
        # MISSION COMPLETE
        # =====================================================

        self.get_logger().info(
            '========================================'
        )

        self.get_logger().info(
            '✓ DELIVERY MISSION COMPLETE'
        )

        self.get_logger().info(
            'HOME -> PICKUP A -> HOME'
        )

        self.get_logger().info(
            '========================================'
        )


# =============================================================
# MAIN
# =============================================================

def main(args=None):

    rclpy.init(args=args)

    node = DeliveryMission()

    try:

        node.run_mission()

    except KeyboardInterrupt:

        node.get_logger().info(
            'Mission interrupted by user.'
        )

    except Exception as e:

        node.get_logger().error(
            f'Mission error: {e}'
        )

    finally:

        node.destroy_node()

        if rclpy.ok():

            rclpy.shutdown()


if __name__ == '__main__':

    main()