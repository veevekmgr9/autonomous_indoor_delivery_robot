#!/usr/bin/env python3

import math
import threading

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

import rclpy
from rclpy.node import Node

from rclpy.action import ActionClient

from nav2_msgs.action import NavigateToPose

# CONFIGURATION
SERVICE_ACCOUNT = (
    "/home/robot/Project/robot_ws/"
    "robot_credentials/firebase-service-account.json"
)

ROBOT_STATE_COLLECTION = "robotState"
ROBOT_STATE_DOCUMENT = "current"

DELIVERIES_COLLECTION = "deliveries"

# ROOM NAVIGATION GOALS
ROOM_GOALS = {

    "HOME": {
        "x": -0.852895,
        "y": -2.22339,
        "yaw": 0.0
    },

    "Room A": {
        "x": -1.56899,
        "y": -1.10715,
        "yaw": 0.70110
    },

    "Room B": {
        "x": -2.799,
        "y": 1.801,
        "yaw": 0.768
    }

}

# FIREBASE + NAV2
class FirebaseNavigationController(Node):

    def __init__(self):

        super().__init__(
            "firebase_navigation_controller"
        )

        # Prevent duplicate navigation goals
        self.processing_lock = (
            threading.Lock()
        )

        self.current_delivery_id = None

        # Normal delivery navigation goal
        self.current_goal_handle = None

        # Separate HOME navigation goal
        self.home_goal_handle = None

        self.current_destination = None
        self.current_phase = None

        # Firebase
        self.firebase_app = (
            firebase_admin.initialize_app(
                credentials.Certificate(
                    SERVICE_ACCOUNT
                )
            )
        )

        self.db = firestore.client()


        self.get_logger().info(
            "Firebase Admin SDK connected"
        )

        # Nav2 action client
        self.nav_client = ActionClient(
            self,
            NavigateToPose,
            "/navigate_to_pose"
        )

        self.get_logger().info(
            "Waiting for /navigate_to_pose..."
        )

        while not self.nav_client.wait_for_server(
            timeout_sec=1.0
        ):

            self.get_logger().warn(
                "/navigate_to_pose not available..."
            )

        self.get_logger().info(
            "/navigate_to_pose is available"
        )

        # Firebase robot state listener
        self.robot_state_ref = (
            self.db
            .collection(
                ROBOT_STATE_COLLECTION
            )
            .document(
                ROBOT_STATE_DOCUMENT
            )
        )

        self.watch = (
            self.robot_state_ref.on_snapshot(
                self.robot_state_callback
            )
        )

        self.get_logger().info(
            "Firebase robot-state listener started"
        )

    # ROBOT STATE CALLBACK
    def robot_state_callback(
        self,
        document_snapshot,
        changes,
        read_time
    ):
        ticket_id = "UNKNOWN"
        active_delivery_id = None
        try:

            if not document_snapshot:
                return


            snapshot = document_snapshot[0]

            if not snapshot.exists:

                self.get_logger().info(
                    "robotState/current does not exist"
                )

                return

            state = snapshot.to_dict()

            active_delivery_id = state.get(
                "activeDeliveryId"
            )

            robot_status = state.get(
                "status",
                "IDLE"
            )

            ticket_id = state.get(
                "ticketId",
                active_delivery_id or "UNKNOWN"
            )

            # ROBOT IDLE
            if not active_delivery_id:

                self.get_logger().info(
                    "Robot is IDLE"
                )

                return

            self.get_logger().info(
                f"Active delivery: "
                f"{ticket_id} → {robot_status}"
            )

            # VERIFIED → RETURN HOME
            if robot_status == "VERIFIED":

                with self.processing_lock:

                    # Prevent sending HOME goal twice

                    if self.current_delivery_id == (
                        active_delivery_id
                    ):

                        if self.current_destination == "HOME":

                            return

                    self.current_delivery_id = (
                        active_delivery_id
                    )

                    self.current_destination = "HOME"

                    self.current_phase = "HOME"

                self.get_logger().info(
                    f"{ticket_id}: "
                    "Receiver verified"
                )

                self.get_logger().info(
                    f"{ticket_id}: "
                    "Returning robot HOME"
                )

                self.start_home_navigation(
                    active_delivery_id,
                    ticket_id
                )

                return

            # STATES THAT DO NOT START NAVIGATION
            if robot_status in (
                "NAVIGATING",
                "NAVIGATING_TO_PICKUP",
                "NAVIGATING_TO_RECEIVER",
                "ARRIVED",
                "ARRIVED_AT_PICKUP",
                "ARRIVED_AT_RECEIVER",
                "RETURNING_HOME",
                "HOME",
                "COMPLETED",
                "NAVIGATION_ERROR",
                "HOME_ERROR"
            ):

                return

            # GET DELIVERY
            delivery_ref = (
                self.db
                .collection(
                    DELIVERIES_COLLECTION
                )
                .document(
                    active_delivery_id
                )
            )

            delivery_snapshot = (
                delivery_ref.get()
            )

            if not delivery_snapshot.exists:

                self.get_logger().error(
                    f"{ticket_id}: "
                    "Delivery document not found"
                )

                self.clear_navigation_state()

                return

            delivery = (
                delivery_snapshot.to_dict()
            )

            destination = delivery.get(
                "destination"
            )

            if not destination:

                self.get_logger().error(
                    f"{ticket_id}: "
                    "Destination is missing"
                )

                self.clear_navigation_state()

                return

            self.get_logger().info(
                f"Destination: {destination}"
            )

            # CHECK DESTINATION
            if destination not in ROOM_GOALS:

                self.get_logger().error(
                    f"{ticket_id}: "
                    f"Unknown destination "
                    f"'{destination}'"
                )

                self.clear_navigation_state()

                return

            # PENDING → ASSIGNED
            if robot_status == "PENDING":

                self.get_logger().info(
                    f"{ticket_id}: "
                    "Robot available - assigning delivery"
                )

                self.update_robot_state(
                    active_delivery_id,
                    ticket_id,
                    "ASSIGNED"
                )

                self.clear_navigation_state()

                return

            # ASSIGNED → PICKUP
            if robot_status == "ASSIGNED":

                pickup_location = delivery.get(
                    "pickupLocation"
                )

                if not pickup_location:

                    self.get_logger().error(
                        f"{ticket_id}: "
                        "Pickup location is missing"
                    )

                    self.clear_navigation_state()

                    return

                if pickup_location not in ROOM_GOALS:

                    self.get_logger().error(
                        f"{ticket_id}: "
                        f"Unknown pickup location "
                        f"'{pickup_location}'"
                    )

                    self.clear_navigation_state()

                    return

                with self.processing_lock:

                    if self.current_goal_handle is not None:

                        self.get_logger().warn(
                            "Navigation goal already active"
                        )

                        return

                    self.current_delivery_id = (
                        active_delivery_id
                    )

                    self.current_destination = (
                        pickup_location
                    )

                    self.current_phase = "PICKUP"

                self.get_logger().info(
                    f"{ticket_id}: "
                    f"Going to pickup location: "
                    f"{pickup_location}"
                )

                self.start_navigation(
                    active_delivery_id,
                    ticket_id,
                    pickup_location,
                    "PICKUP"
                )
                return

            # SEND TO RECEIVER
            if robot_status == "SEND_TO_RECEIVER":

                destination = delivery.get(
                    "destination"
                )

                if not destination:

                    self.get_logger().error(
                        f"{ticket_id}: "
                        "Destination is missing"
                    )

                    self.clear_navigation_state()

                    return

                if destination not in ROOM_GOALS:

                    self.get_logger().error(
                        f"{ticket_id}: "
                        f"Unknown destination "
                        f"'{destination}'"
                    )

                    self.clear_navigation_state()

                    return

                with self.processing_lock:

                    if self.current_goal_handle is not None:

                        self.get_logger().warn(
                            "Navigation goal already active"
                        )

                        return

                    self.current_delivery_id = (
                        active_delivery_id
                    )

                    self.current_destination = (
                        destination
                    )

                    self.current_phase = "RECEIVER"

                self.get_logger().info(
                    f"{ticket_id}: "
                    "Robot is delivering to receiver "
                    f"Destination: {destination}"
                )

                self.start_navigation(
                    active_delivery_id,
                    ticket_id,
                    destination,
                    "RECEIVER"
                )

                return

            # RETURN HOME COMMAND
            if robot_status == "RETURN_HOME":

                self.get_logger().warn(
                    f"{ticket_id}: "
                    "Return-home command received"
                )

                # Cancel current delivery goal
                if self.current_goal_handle is not None:

                    self.get_logger().warn(
                        "Cancelling current Nav2 goal..."
                    )

                    goal_to_cancel = (
                        self.current_goal_handle
                    )

                    # Clear the normal goal handle first

                    self.current_goal_handle = None

                    cancel_future = (
                        goal_to_cancel
                        .cancel_goal_async()
                    )

                    cancel_future.add_done_callback(
                        lambda future:
                        self.send_home_after_cancel(
                            future,
                            active_delivery_id,
                            ticket_id
                        )
                    )

                else:
                    # No active delivery goal.
                    # Send HOME directly.
                    self.send_home_after_cancel(
                        None,
                        active_delivery_id,
                        ticket_id
                    )

                return

        except Exception as e:

            self.get_logger().error(
                f"{ticket_id}: "
                f"Robot state callback error: {e}"
            )

            self.clear_navigation_state()

    # START NORMAL NAVIGATION
    def start_navigation(
        self,
        delivery_id,
        ticket_id,
        destination,
        phase
    ):
        goal = ROOM_GOALS[
            destination
        ]

        self.get_logger().info(
            f"Sending robot to "
            f"{destination}"
        )

        self.get_logger().info(
            f"Goal position: "
            f"x={goal['x']}, "
            f"y={goal['y']}, "
            f"yaw={goal['yaw']}"
        )

        # Create Nav2 goal
        goal_msg = (
            NavigateToPose.Goal()
        )

        goal_msg.pose.header.frame_id = (
            "map"
        )

        goal_msg.pose.header.stamp = (
            self.get_clock()
            .now()
            .to_msg()
        )

        goal_msg.pose.pose.position.x = (
            goal["x"]
        )

        goal_msg.pose.pose.position.y = (
            goal["y"]
        )

        goal_msg.pose.pose.position.z = (
            0.0
        )

        # Convert yaw to quaternion
        yaw = goal["yaw"]

        goal_msg.pose.pose.orientation.z = (
            math.sin(yaw / 2.0)
        )

        goal_msg.pose.pose.orientation.w = (
            math.cos(yaw / 2.0)
        )

        # Update Firebase
        if phase == "PICKUP":

            navigation_status = (
                "NAVIGATING_TO_PICKUP"
            )

        else:
            navigation_status = (
                "NAVIGATING_TO_RECEIVER"
            )

        self.update_robot_state(
            delivery_id,
            ticket_id,
            navigation_status
        )

        # Send goal to Nav2
        send_future = (
            self.nav_client
            .send_goal_async(
                goal_msg,
                feedback_callback=(
                    self.navigation_feedback
                )
            )
        )

        send_future.add_done_callback(
            lambda future:
                self.goal_response_callback(
                    future,
                    delivery_id,
                    ticket_id,
                    phase
                )
        )

    # NAV2 GOAL RESPONSE
    def goal_response_callback(
        self,
        future,
        delivery_id,
        ticket_id,
        phase
    ):

        try:

            goal_handle = (
                future.result()
            )

        except Exception as e:

            self.get_logger().error(
                f"{ticket_id}: "
                f"Nav2 goal error: {e}"
            )

            self.navigation_failed(
                delivery_id,
                ticket_id,
                str(e)
            )

            return

        if not goal_handle.accepted:

            self.get_logger().error(
                f"{ticket_id}: "
                "Nav2 rejected navigation goal"
            )

            self.navigation_failed(
                delivery_id,
                ticket_id,
                "Nav2 rejected goal"
            )

            return

        self.current_goal_handle = (
            goal_handle
        )

        self.get_logger().info(
            f"{ticket_id}: "
            "Nav2 goal accepted"
        )

        result_future = (
            goal_handle
            .get_result_async()
        )

        result_future.add_done_callback(
            lambda future:
                self.navigation_result_callback(
                    future,
                    delivery_id,
                    ticket_id,
                    phase
                )
        )

    # NAV2 FEEDBACK
    def navigation_feedback(
        self,
        feedback_msg
    ):

        feedback = (
            feedback_msg.feedback
        )

        distance = (
            feedback.distance_remaining
        )

        current_pose = (
            feedback.current_pose.pose
        )

        x = current_pose.position.x
        y = current_pose.position.y

        # self.get_logger().info(
        #     f"Robot position: "
        #     f"x={x:.2f}, "
        #     f"y={y:.2f}, "
        #     f"distance remaining="
        #     f"{distance:.2f} m"
        # )

    # NAV2 RESULT
    def navigation_result_callback(
        self,
        future,
        delivery_id,
        ticket_id,
        phase
    ):

        try:

            result = (
                future.result()
            )

            status = (
                result.status
            )

            self.get_logger().info(
                f"{ticket_id}: "
                f"Nav2 result status = "
                f"{status}"
            )

            # SUCCESS
            if status == 4:

                self.get_logger().info(
                    f" {ticket_id}: "
                    "Robot reached destination"
                )

                self.navigation_success(
                    delivery_id,
                    ticket_id,
                    phase
                )

            else:

                self.get_logger().error(
                    f"{ticket_id}: "
                    "Navigation failed"
                )

                self.navigation_failed(
                    delivery_id,
                    ticket_id,
                    f"Nav2 status {status}"
                )

        except Exception as e:

            self.get_logger().error(
                f"{ticket_id}: "
                f"Navigation result error: {e}"
            )

            self.navigation_failed(
                delivery_id,
                ticket_id,
                str(e)
            )

    # NAVIGATION SUCCESS
    def navigation_success(
        self,
        delivery_id,
        ticket_id,
        phase
    ):

        self.get_logger().info(
            f"🔵 {ticket_id}: "
            "Setting delivery ARRIVED"
        )

        delivery_ref = (
            self.db
            .collection(
                DELIVERIES_COLLECTION
            )
            .document(
                delivery_id
            )
        )

        # Pickup
        if phase == "PICKUP":

            self.get_logger().info(
                f"{ticket_id}: "
                "Robot arrived at pickup location"
            )

            delivery_ref.update(
                {
                    "status": "ARRIVED_AT_PICKUP",
                    "arrivedAt":
                        firestore.SERVER_TIMESTAMP
                }
            )

            self.update_robot_state(
                delivery_id,
                ticket_id,
                "ARRIVED_AT_PICKUP"
            )

            self.clear_navigation_state()

            return

        # Receiver
        if phase == "RECEIVER":

            self.get_logger().info(
                f"{ticket_id}: "
                "Robot arrived at receiver location"
            )

            delivery_ref.update(
                {
                    "status": "ARRIVED",
                    "arrivedAt":
                        firestore.SERVER_TIMESTAMP
                }
            )

            self.update_robot_state(
                delivery_id,
                ticket_id,
                "ARRIVED"
            )

            self.clear_navigation_state()

            return

        # HOME
        if phase == "HOME":
            self.get_logger().info(
                f"{ticket_id}: "
                "Robot successfully returned HOME"
            )

            delivery_ref.update(
                {
                    "status": "CANCELLED",
                    "returnHomeCompleted": True,
                    "returnedHomeAt":
                        firestore.SERVER_TIMESTAMP
                }
            )

            self.update_robot_state(
                delivery_id,
                ticket_id,
                "HOME"
            )

            self.clear_navigation_state()
            return

    # NAVIGATION FAILURE
    def navigation_failed(
        self,
        delivery_id,
        ticket_id,
        reason
    ):
        self.get_logger().error(
            f"❌ {ticket_id}: "
            f"Navigation failed: "
            f"{reason}"
        )

        self.update_robot_state(
            delivery_id,
            ticket_id,
            "NAVIGATION_ERROR"
        )

        self.clear_navigation_state()

    # UPDATE ROBOT STATE
    def update_robot_state(
        self,
        delivery_id,
        ticket_id,
        status
    ):

        try:

            self.robot_state_ref.set(
                {
                    "activeDeliveryId":
                        delivery_id,

                    "ticketId":
                        ticket_id,

                    "status":
                        status,

                    "robotStatus":
                        status,

                    "updatedAt":
                        firestore.SERVER_TIMESTAMP
                },
                merge=True
            )

        except Exception as e:

            self.get_logger().error(
                f"Failed to update robot state: "
                f"{e}"
            )

    # CLEAR NAVIGATION STATE
    def clear_navigation_state(
        self
    ):

        with self.processing_lock:

            self.current_delivery_id = None

            self.current_goal_handle = None

            self.home_goal_handle = None

            self.current_destination = None

            self.current_phase = None

    # HOME RETURN
    def start_home_navigation(
        self,
        delivery_id,
        ticket_id
    ):

        goal = ROOM_GOALS[
            "HOME"
        ]

        self.get_logger().info(
            f"🏠 Sending robot HOME"
        )

        self.get_logger().info(
            f"HOME position: "
            f"x={goal['x']}, "
            f"y={goal['y']}, "
            f"yaw={goal['yaw']}"
        )

        # Create Nav2 goal
        goal_msg = (
            NavigateToPose.Goal()
        )

        goal_msg.pose.header.frame_id = (
            "map"
        )

        goal_msg.pose.header.stamp = (
            self.get_clock()
            .now()
            .to_msg()
        )

        goal_msg.pose.pose.position.x = (
            goal["x"]
        )

        goal_msg.pose.pose.position.y = (
            goal["y"]
        )

        goal_msg.pose.pose.position.z = (
            0.0
        )

        # Convert yaw to quaternion
        yaw = goal["yaw"]

        goal_msg.pose.pose.orientation.z = (
            math.sin(yaw / 2.0)
        )

        goal_msg.pose.pose.orientation.w = (
            math.cos(yaw / 2.0)
        )

        # Update Firebase
        self.update_robot_state(
            delivery_id,
            ticket_id,
            "RETURNING_HOME"
        )

        # Send HOME goal
        send_future = (
            self.nav_client
            .send_goal_async(
                goal_msg,
                feedback_callback=(
                    self.home_navigation_feedback
                )
            )
        )

        send_future.add_done_callback(
            lambda future:
                self.home_goal_response_callback(
                    future,
                    delivery_id,
                    ticket_id
                )
        )

    # HOME NAVIGATION FEEDBACK
    def home_navigation_feedback(
        self,
        feedback_msg
    ):

        feedback = (
            feedback_msg.feedback
        )

        distance = (
            feedback.distance_remaining
        )

        current_pose = (
            feedback.current_pose.pose
        )

        x = current_pose.position.x
        y = current_pose.position.y

        self.get_logger().info(
            f"Robot returning HOME: "
            f"x={x:.2f}, "
            f"y={y:.2f}, "
            f"distance remaining="
            f"{distance:.2f} m"
        )

    # HOME GOAL RESPONSE
    def home_goal_response_callback(
        self,
        future,
        delivery_id,
        ticket_id
    ):

        try:

            goal_handle = (
                future.result()
            )

        except Exception as e:

            self.get_logger().error(
                f"{ticket_id}: "
                f"HOME Nav2 goal error: {e}"
            )

            self.home_navigation_failed(
                delivery_id,
                ticket_id,
                str(e)
            )

            return

        if not goal_handle.accepted:

            self.get_logger().error(
                f"{ticket_id}: "
                "Nav2 rejected HOME goal"
            )

            self.home_navigation_failed(
                delivery_id,
                ticket_id,
                "Nav2 rejected HOME goal"
            )

            return

        # Store HOME goal separately
        self.home_goal_handle = (
            goal_handle
        )

        self.get_logger().info(
            f"{ticket_id}: "
            "HOME goal accepted"
        )

        result_future = (
            goal_handle
            .get_result_async()
        )

        result_future.add_done_callback(
            lambda future:
                self.home_navigation_result_callback(
                    future,
                    delivery_id,
                    ticket_id
                )
        )

    # HOME NAVIGATION RESULT
    def home_navigation_result_callback(
        self,
        future,
        delivery_id,
        ticket_id
    ):

        try:

            result = (
                future.result()
            )


            status = (
                result.status
            )


            self.get_logger().info(
                f"{ticket_id}: "
                f"HOME Nav2 result status = "
                f"{status}"
            )


            # ROS action status 4 = SUCCESS
            if status == 4:

                self.get_logger().info(
                    f"{ticket_id}: "
                    "Robot successfully returned HOME"
                )

                self.complete_delivery(
                    delivery_id,
                    ticket_id
                )

            else:

                self.get_logger().error(
                    f"{ticket_id}: "
                    "Robot failed to return HOME"
                )

                self.home_navigation_failed(
                    delivery_id,
                    ticket_id,
                    f"Nav2 status {status}"
                )

        except Exception as e:

            self.get_logger().error(
                f"{ticket_id}: "
                f"HOME result error: {e}"
            )

            self.home_navigation_failed(
                delivery_id,
                ticket_id,
                str(e)
            )

    # COMPLETE DELIVERY
    def complete_delivery(
        self,
        delivery_id,
        ticket_id
    ):

        self.get_logger().info(
            f"{ticket_id}: "
            "Delivery completed"
        )

        # Update delivery
        delivery_ref = (
            self.db
            .collection(
                DELIVERIES_COLLECTION
            )
            .document(
                delivery_id
            )
        )

        delivery_ref.update(
            {
                "status": "COMPLETED",
                "completedAt":
                    firestore.SERVER_TIMESTAMP
            }
        )

        # Robot becomes IDLE
        self.robot_state_ref.set(
            {
                "activeDeliveryId": None,
                "ticketId": None,
                "status": "IDLE",
                "robotStatus": "IDLE",
                "robotId": None,
                "updatedAt":
                    firestore.SERVER_TIMESTAMP
            }
        )

        self.clear_navigation_state()

        self.get_logger().info(
            "Robot is now IDLE"
        )

        self.get_logger().info(
            "Ready for next delivery"
        )

    # HOME NAVIGATION FAILURE
    def home_navigation_failed(
        self,
        delivery_id,
        ticket_id,
        reason
    ):

        self.get_logger().error(
            f"{ticket_id}: "
            f"HOME navigation failed: "
            f"{reason}"
        )


        self.update_robot_state(
            delivery_id,
            ticket_id,
            "HOME_ERROR"
        )

        self.clear_navigation_state()

    # SEND HOME AFTER CANCE
    def send_home_after_cancel(
        self,
        future,
        delivery_id,
        ticket_id
    ):

        self.get_logger().info(
            f"{ticket_id}: "
            "Current navigation goal cancelled."
        )

        with self.processing_lock:
            self.current_goal_handle = None
            self.current_delivery_id = (
                delivery_id
            )
            self.current_destination = "HOME"
            self.current_phase = "HOME"

        # Check HOME exists
        if "HOME" not in ROOM_GOALS:

            self.get_logger().error(
                "HOME location is not defined "
                "in ROOM_GOALS."
            )

            self.update_robot_state(
                delivery_id,
                ticket_id,
                "HOME_ERROR"
            )

            self.clear_navigation_state()

            return

        self.get_logger().info(
            f"{ticket_id}: "
            "Sending robot back to HOME."
        )

        # Use the dedicated HOME navigation function
        self.start_home_navigation(
            delivery_id,
            ticket_id
        )

    # CLEANUP
    def shutdown_firebase(
        self
    ):

        try:

            self.watch.unsubscribe()

        except Exception:
            pass

# MAIN
def main(args=None):

    rclpy.init(
        args=args
    )

    node = (
        FirebaseNavigationController()
    )

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.shutdown_firebase()
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":

    main()