#!/usr/bin/env python3

import time
import threading

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

import rclpy
from rclpy.node import Node

from std_srvs.srv import Trigger

# CONFIGURATION
SERVICE_ACCOUNT = (
    "/home/robot/Project/robot_ws/"
    "robot_credentials/firebase-service-account.json"
)

FIREBASE_COLLECTION = "deliveries"

# FIREBASE + ROS2 MONITOR
class FirebaseRobotMonitor(Node):

    def __init__(self):

        super().__init__(
            "firebase_robot_monitor")
        
        # ROS2 SERVICES
        # Authentication service
        self.auth_client = self.create_client(
            Trigger,
            "/authenticate_receiver"
        )

        # Delivery arrived service
        self.arrived_client = self.create_client(
            Trigger,
            "/delivery_arrived"
        )

        # Authentication failed service
        self.failed_client = self.create_client(
            Trigger,
            "/authentication_failed"
        )

        # WAIT FOR AUTHENTICATION SERVICE
        self.get_logger().info(
            "Waiting for /authenticate_receiver..."
        )

        while not self.auth_client.wait_for_service(
            timeout_sec=1.0
        ):

            self.get_logger().warn(
                "/authenticate_receiver not available yet..."
            )

        self.get_logger().info(
            "/authenticate_receiver is available"
        )

        # WAIT FOR ARRIVED SERVICE
        self.get_logger().info(
            "Waiting for /delivery_arrived..."
        )

        while not self.arrived_client.wait_for_service(
            timeout_sec=1.0
        ):

            self.get_logger().warn(
                "/delivery_arrived not available yet..."
            )

        self.get_logger().info(
            "/delivery_arrived is available"
        )

        # WAIT FOR FAILED SERVICE
        self.get_logger().info(
            "Waiting for /authentication_failed..."
        )

        while not self.failed_client.wait_for_service(
            timeout_sec=1.0
        ):

            self.get_logger().warn(
                "/authentication_failed not available yet..."
            )

        self.get_logger().info(
            "/authentication_failed is available"
        )

        # PREVENT DUPLICATE PROCESSING
        self.processed_arrivals = set()

        self.processed_deliveries = set()

        self.processing_lock = threading.Lock()

        self.last_authentication_attempts = {}

        # FIREBASE
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

        # FIREBASE ROBOT STATE LISTENER
        self.robot_state_ref = (
            self.db
            .collection("robotState")
            .document("current")
        )

        self.watch = (
            self.robot_state_ref.on_snapshot(
                self.robot_state_callback
            )
        )

        self.get_logger().info(
            "Firebase active-delivery listener started"
        )

    # ROBOT STATE CALLBACK
    def robot_state_callback(
        self,
        document_snapshot,
        changes,
        read_time
    ):

        for document in document_snapshot:

            if not document.exists:

                self.get_logger().info(
                    "No robot state document found"
                )

                continue

            state = document.to_dict()

            active_delivery_id = state.get(
                "activeDeliveryId"
            )

            status = state.get(
                "status"
            )

            ticket_id = state.get(
                "ticketId",
                active_delivery_id
            )

            # ROBOT IDLE
            if not active_delivery_id:

                self.get_logger().info(
                    "Robot is currently IDLE"
                )

                continue

            # ACTIVE DELIVERY
            self.get_logger().info(
                f"Active delivery: "
                f"{ticket_id} → {status}"
            )

            # FETCH ONLY ACTIVE DELIVERY
            try:

                delivery_ref = (
                    self.db
                    .collection(
                        "deliveries"
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
                        "Active delivery document "
                        "not found"
                    )

                    continue

                delivery = (
                    delivery_snapshot.to_dict()
                )

                # Add ID for consistency
                delivery["id"] = (
                    active_delivery_id
                )

                # Use actual delivery ticket
                ticket_id = delivery.get(
                    "ticketId",
                    ticket_id
                )

                if (
                    not hasattr(
                        self,
                        "current_active_delivery_id"
                    )
                ):

                    self.current_active_delivery_id = None

                if (
                    self.current_active_delivery_id
                    != active_delivery_id
                ):

                    self.get_logger().info(
                        f"Active delivery changed: "
                        f"{ticket_id}"
                    )

                    self.current_active_delivery_id = (
                        active_delivery_id
                    )

                    # Reset processing state for new delivery
                    with self.processing_lock:

                        self.processed_arrivals.discard(
                            active_delivery_id
                        )

                        self.processed_deliveries.discard(
                            active_delivery_id
                        )

                        self.last_authentication_attempts.pop(
                            active_delivery_id,
                            None
                        )

                # PROCESS ACTIVE DELIVERY
                self.process_active_delivery(
                    active_delivery_id,
                    ticket_id,
                    delivery
                )

            except Exception as e:

                self.get_logger().error(
                    f"Failed to read active delivery: {e}"
                )

    # DELIVERY ARRIVED
    def delivery_arrived(
        self,
        delivery_id,
        ticket_id
    ):

        self.get_logger().info(
            f"{ticket_id}: "
            "Delivery arrived - setting LED BLUE"
        )

        request = Trigger.Request()

        future = (
            self.arrived_client.call_async(
                request
            )
        )

        while (
            not future.done()
            and rclpy.ok()
        ):

            time.sleep(0.05)

        if not future.done():

            self.get_logger().error(
                f"{ticket_id}: "
                "Delivery-arrived service timeout"
            )

            return

        try:

            response = future.result()

        except Exception as e:

            self.get_logger().error(
                f"{ticket_id}: "
                f"Delivery-arrived service error: {e}"
            )

            return

        if response.success:

            self.get_logger().info(
                f"{ticket_id}: "
                f"{response.message}"
            )

        else:

            self.get_logger().error(
                f"{ticket_id}: "
                f"Failed to set ARRIVED LED: "
                f"{response.message}"
            )

    # AUTHENTICATE RECEIVER
    def authenticate_delivery(
        self,
        delivery_id,
        ticket_id,
        data
    ):

        self.get_logger().info(
            f"🔐 Authenticating delivery "
            f"{ticket_id}"
        )

        # CHECK RECEIVER ID
        receiver_id = data.get(
            "receiverId"
        )

        if not receiver_id:

            self.get_logger().error(
                f"{ticket_id}: receiverId missing"
            )

            self.authentication_failed(
                ticket_id
            )

            return

        self.get_logger().info(
            f"Receiver: {receiver_id}"
        )

        # CREATE AUTH REQUEST
        request = Trigger.Request()

        future = (
            self.auth_client.call_async(
                request
            )
        )

        # WAIT FOR RESPONSE
        while (
            not future.done()
            and rclpy.ok()
        ):
            time.sleep(0.05)

        if not future.done():

            self.get_logger().error(
                f"{ticket_id}: "
                "Authentication service timeout"
            )

            self.authentication_failed(
                ticket_id
            )

            return

        try:

            response = future.result()

        except Exception as e:

            self.get_logger().error(
                f"{ticket_id}: "
                f"ROS2 service error: {e}"
            )

            self.authentication_failed(
                ticket_id
            )

            return

        # AUTHENTICATION SUCCESS
        if response.success:

            self.get_logger().info(
                f"{ticket_id}: "
                "Authentication handshake successful"
            )

            self.get_logger().info(
                f"Arduino response: "
                f"{response.message}"
            )

        # AUTHENTICATION FAILURE
        else:

            self.get_logger().error(
                f"{ticket_id}: "
                "Authentication handshake failed"
            )

            self.get_logger().error(
                response.message
            )

            self.authentication_failed(
                ticket_id
            )

    # AUTHENTICATION FAILED
    def authentication_failed(
        self,
        ticket_id
    ):

        self.get_logger().warn(
            f"🔴 {ticket_id}: "
            "Setting authentication error LED"
        )

        request = Trigger.Request()

        future = (
            self.failed_client.call_async(
                request
            )
        )

        while (
            not future.done()
            and rclpy.ok()
        ):

            time.sleep(0.05)

        if not future.done():

            self.get_logger().error(
                f"{ticket_id}: "
                "Authentication-failed service timeout"
            )

            return

        try:

            response = future.result()

        except Exception as e:

            self.get_logger().error(
                f"{ticket_id}: "
                f"Authentication-failed service error: {e}"
            )

            return

        if response.success:

            self.get_logger().info(
                f"🔴 {ticket_id}: "
                f"{response.message}"
            )

        else:

            self.get_logger().error(
                f"{ticket_id}: "
                f"Failed to set error LED: "
                f"{response.message}"
            )

    # CLEANUP
    def shutdown_firebase(self):

        try:

            self.watch.unsubscribe()

        except Exception:
            pass

    # PROCESS ACTIVE DELIVERY
    def process_active_delivery(
        self,
        delivery_id,
        ticket_id,
        data
    ):

        status = data.get(
            "status"
        )

        # FACE AUTHENTICATION FAILURE
        authentication_attempt_at = (
            data.get(
                "authenticationAttemptAt"
            )
        )

        if authentication_attempt_at is not None:

            attempt_value = str(
                authentication_attempt_at
            )

            with self.processing_lock:

                previous_attempt = (
                    self.last_authentication_attempts
                    .get(delivery_id)
                )

                if (
                    previous_attempt
                    != attempt_value
                ):

                    self.last_authentication_attempts[
                        delivery_id
                    ] = attempt_value

                    self.get_logger().warn(
                        f"{ticket_id}: "
                        "Face authentication failed"
                    )

                    self.authentication_failed(
                        ticket_id
                    )


        if status == "ARRIVED_AT_PICKUP":
            with self.processing_lock:
                if delivery_id in self.processed_arrivals:
                    return

                self.processed_arrivals.add(delivery_id)

            self.get_logger().info(
                f"{ticket_id}: "
                f"Pickup reached - turning LED ON"
            )

            self.delivery_arrived(
                delivery_id,
                ticket_id
            )

        # ARRIVED
        if status == "ARRIVED":

            with self.processing_lock:

                if (
                    delivery_id
                    in self.processed_arrivals
                ):

                    self.get_logger().info(
                        f"{ticket_id} already "
                        "marked ARRIVED - ignoring"
                    )

                else:

                    self.processed_arrivals.add(
                        delivery_id
                    )


                    self.delivery_arrived(
                        delivery_id,
                        ticket_id
                    )

        # VERIFIED
        if status == "VERIFIED":

            with self.processing_lock:

                if (
                    delivery_id
                    in self.processed_deliveries
                ):

                    self.get_logger().info(
                        f"{ticket_id} already "
                        "authenticated - ignoring"
                    )

                    return


                self.processed_deliveries.add(
                    delivery_id
                )


            self.authenticate_delivery(
                delivery_id,
                ticket_id,
                data
            )

# MAIN
def main(args=None):

    rclpy.init(
        args=args
    )

    node = FirebaseRobotMonitor()

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