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
        # MISSION SETTINGS
        # =====================================================

        # Number of attempts for each destination
        self.max_retries = 2

        # Wait between successful destinations
        self.wait_between_goals = 2.0

        # Maximum time allowed for one navigation goal
        self.goal_timeout = 120.0

        # =====================================================
        # SAVED MAP LOCATIONS
        # =====================================================

        # -----------------------------------------------------
        # HOME
        # -----------------------------------------------------

        self.home = {
            'x': -0.852895,
            'y': -2.22339,
            'yaw': 0.0
        }

        # -----------------------------------------------------
        # PICKUP A
        # -----------------------------------------------------

        self.pickup_a = {
            'x': -1.56899,
            'y': -1.10715,
            'yaw': 0.70110
        }

        # -----------------------------------------------------
        # PICKUP B
        # -----------------------------------------------------

        self.pickup_b = {
            'x': -2.799,
            'y': 1.801,
            'yaw': 0.768
        }

        # =====================================================
        # NAV2 ACTION CLIENT
        # =====================================================

        self.nav_to_pose = ActionClient(
            self,
            NavigateToPose,
            '/navigate_to_pose'
        )

        self.get_logger().info(
            '=========================================='
        )

        self.get_logger().info(
            'Delivery Mission Node Started'
        )

        self.get_logger().info(
            'Mission: HOME -> A -> B -> A -> HOME'
        )

        self.get_logger().info(
            '=========================================='
        )

    # =========================================================
    # CREATE NAV2 GOAL
    # =========================================================

    def make_goal(self, location):

        goal = NavigateToPose.Goal()

        pose = PoseStamped()

        pose.header.frame_id = 'map'

        pose.header.stamp = (
            self.get_clock().now().to_msg()
        )

        pose.pose.position.x = location['x']
        pose.pose.position.y = location['y']
        pose.pose.position.z = 0.0

        # -----------------------------------------------------
        # Convert yaw to quaternion
        # -----------------------------------------------------

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
            'Waiting for Nav2 NavigateToPose server...'
        )

        available = (
            self.nav_to_pose.wait_for_server(
                timeout_sec=10.0
            )
        )

        if not available:

            self.get_logger().error(
                'Nav2 NavigateToPose action server '
                'is not available.'
            )

            return False

        self.get_logger().info(
            'Nav2 NavigateToPose server available.'
        )

        return True

    # =========================================================
    # SEND ONE GOAL
    # =========================================================

    def send_goal(self, name, location):

        self.get_logger().info(
            '------------------------------------------'
        )

        self.get_logger().info(
            f'Going to {name}'
        )

        self.get_logger().info(
            f'Goal: '
            f'x={location["x"]:.3f}, '
            f'y={location["y"]:.3f}, '
            f'yaw={location["yaw"]:.3f}'
        )

        goal = self.make_goal(location)

        # -----------------------------------------------------
        # Send goal
        # -----------------------------------------------------

        send_future = (
            self.nav_to_pose.send_goal_async(goal)
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
                f'Nav2 rejected goal for {name}.'
            )

            return False

        self.get_logger().info(
            f'Goal accepted: {name}'
        )

        # -----------------------------------------------------
        # Wait for result
        # -----------------------------------------------------

        result_future = (
            goal_handle.get_result_async()
        )

        start_time = time.monotonic()

        while not result_future.done():

            rclpy.spin_once(
                self,
                timeout_sec=0.2
            )

            elapsed = (
                time.monotonic() -
                start_time
            )

            # -------------------------------------------------
            # Timeout
            # -------------------------------------------------

            if elapsed > self.goal_timeout:

                self.get_logger().warn(
                    f'{name} exceeded '
                    f'{self.goal_timeout:.0f}s timeout.'
                )

                self.get_logger().warn(
                    f'Cancelling {name} goal...'
                )

                cancel_future = (
                    goal_handle.cancel_goal_async()
                )

                rclpy.spin_until_future_complete(
                    self,
                    cancel_future
                )

                self.get_logger().error(
                    f'{name} navigation timed out.'
                )

                return False

        # -----------------------------------------------------
        # Get result
        # -----------------------------------------------------

        result = result_future.result()

        if result is None:

            self.get_logger().error(
                f'No navigation result received '
                f'for {name}.'
            )

            return False

        status = result.status

        # -----------------------------------------------------
        # Success
        # -----------------------------------------------------

        if status == GoalStatus.STATUS_SUCCEEDED:

            self.get_logger().info(
                f'✓ Successfully reached {name}'
            )

            return True

        # -----------------------------------------------------
        # Cancelled
        # -----------------------------------------------------

        if status == GoalStatus.STATUS_CANCELED:

            self.get_logger().warn(
                f'{name} navigation was cancelled.'
            )

            return False

        # -----------------------------------------------------
        # Failed
        # -----------------------------------------------------

        self.get_logger().error(
            f'Navigation to {name} failed.'
        )

        self.get_logger().error(
            f'Nav2 status = {status}'
        )

        return False

    # =========================================================
    # GO TO LOCATION WITH RETRIES
    # =========================================================

    def go_to(self, name, location):

        for attempt in range(
            1,
            self.max_retries + 1
        ):

            self.get_logger().info(
                '=========================================='
            )

            self.get_logger().info(
                f'{name}: attempt '
                f'{attempt}/{self.max_retries}'
            )

            success = self.send_goal(
                name,
                location
            )

            if success:

                self.get_logger().info(
                    f'{name} completed successfully.'
                )

                # -------------------------------------------------
                # Small pause after reaching destination
                # -------------------------------------------------

                self.get_logger().info(
                    f'Waiting '
                    f'{self.wait_between_goals:.1f}s '
                    f'before next destination...'
                )

                time.sleep(
                    self.wait_between_goals
                )

                return True

            # -----------------------------------------------------
            # Failed attempt
            # -----------------------------------------------------

            if attempt < self.max_retries:

                self.get_logger().warn(
                    f'{name} failed.'
                )

                self.get_logger().warn(
                    'Retrying destination...'
                )

                time.sleep(2.0)

            else:

                self.get_logger().error(
                    f'{name} failed after '
                    f'{self.max_retries} attempts.'
                )

        return False

    # =========================================================
    # COMPLETE DELIVERY MISSION
    # =========================================================

    def run_mission(self):

        self.get_logger().info(
            '=========================================='
        )

        self.get_logger().info(
            'STARTING DELIVERY MISSION'
        )

        self.get_logger().info(
            'HOME -> PICKUP A -> PICKUP B -> '
            'PICKUP A -> HOME'
        )

        self.get_logger().info(
            '=========================================='
        )

        # -----------------------------------------------------
        # Check Nav2
        # -----------------------------------------------------

        if not self.wait_for_nav2():

            self.get_logger().error(
                'Mission cannot start because Nav2 '
                'is unavailable.'
            )

            return False

        # =====================================================
        # 1. HOME -> PICKUP A
        # =====================================================

        if not self.go_to(
            'PICKUP A',
            self.pickup_a
        ):

            self.get_logger().error(
                'MISSION FAILED: Could not reach PICKUP A.'
            )

            return False

        self.get_logger().info(
            'PICKUP A reached.'
        )

        self.get_logger().info(
            'Simulating pickup/loading at A...'
        )

        time.sleep(2.0)

        # =====================================================
        # 2. PICKUP A -> PICKUP B
        # =====================================================

        if not self.go_to(
            'PICKUP B',
            self.pickup_b
        ):

            self.get_logger().error(
                'MISSION FAILED: Could not reach PICKUP B.'
            )

            return False

        self.get_logger().info(
            'PICKUP B reached.'
        )

        self.get_logger().info(
            'Simulating pickup/loading at B...'
        )

        time.sleep(2.0)

        # =====================================================
        # 3. PICKUP B -> PICKUP A
        # =====================================================

        if not self.go_to(
            'PICKUP A',
            self.pickup_a
        ):

            self.get_logger().error(
                'MISSION FAILED: Could not return to PICKUP A.'
            )

            return False

        self.get_logger().info(
            'Returned successfully to PICKUP A.'
        )

        # =====================================================
        # 4. PICKUP A -> HOME
        # =====================================================

        if not self.go_to(
            'HOME',
            self.home
        ):

            self.get_logger().error(
                'MISSION FAILED: Could not return HOME.'
            )

            return False

        # =====================================================
        # COMPLETE
        # =====================================================

        self.get_logger().info(
            '=========================================='
        )

        self.get_logger().info(
            '✓ DELIVERY MISSION COMPLETE'
        )

        self.get_logger().info(
            'HOME -> A -> B -> A -> HOME'
        )

        self.get_logger().info(
            '=========================================='
        )

        return True


# =============================================================
# MAIN
# =============================================================

def main(args=None):

    rclpy.init(args=args)

    node = DeliveryMission()

    try:

        success = node.run_mission()

        if success:

            node.get_logger().info(
                'Mission finished successfully.'
            )

        else:

            node.get_logger().error(
                'Mission finished with errors.'
            )

    except KeyboardInterrupt:

        node.get_logger().warn(
            'Mission interrupted by user.'
        )

    except Exception as e:

        node.get_logger().error(
            f'Unexpected mission error: {e}'
        )

    finally:

        node.destroy_node()

        if rclpy.ok():

            rclpy.shutdown()


if __name__ == '__main__':

    main()