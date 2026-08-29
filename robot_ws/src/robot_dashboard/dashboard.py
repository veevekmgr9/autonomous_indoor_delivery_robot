#!/usr/bin/env python3

import subprocess
import threading
import time

from flask import Flask, Response, render_template_string, jsonify

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan, Imu
from std_msgs.msg import String, Int32MultiArray

# FLAS
app = Flask(__name__)

# ROS 2 CONTROL NODE
class RobotControl(Node):

    def __init__(self):

        super().__init__("phone_dashboard")

        # PUBLISHERS
        self.cmd_pub = self.create_publisher(
            Twist,
            "/cmd_vel",
            10
        )

        self.motion_pub = self.create_publisher(
            String,
            "/motion_state",
            10
        )

        # SUBSCRIBERS
        self.create_subscription(
            Odometry,
            "/odometry/filtered",
            self.odom_callback,
            10
        )

        self.create_subscription(
            Int32MultiArray,
            "/wheel_ticks",
            self.encoder_callback,
            10
        )

        self.create_subscription(
            LaserScan,
            "/scan",
            self.scan_callback,
            10
        )

        self.create_subscription(
            Imu,
            "/imu/data_raw",
            self.imu_callback,
            10
        )

        # SPEED SETTINGS
        # Slow speed is recommended while testing SLAM
        self.speed = 0.05
        self.turn = 0.08

        self.min_speed = 0.05
        self.max_speed = 0.25

        self.min_turn = 0.08
        self.max_turn = 0.60

        # CONTROL STATE
        self.current_command = "stop"

        self.valid_commands = {
            "forward",
            "backward",
            "left",
            "right",
            "stop"
        }

        self.command_lock = threading.Lock()

        # SENSOR STATE
        self.x = 0.0
        self.y = 0.0

        self.linear_velocity = 0.0
        self.angular_velocity = 0.0

        self.left_ticks = 0
        self.right_ticks = 0

        self.last_scan_time = 0.0
        self.last_odom_time = 0.0
        self.last_imu_time = 0.0
        self.last_encoder_time = 0.0

        self.front_distance = None

        # CONTROL TIMER
        # Publish cmd_vel at 100 Hz
        self.timer = self.create_timer(
            0.01,
            self.publish_command
        )

        self.get_logger().info(
            "Phone dashboard ROS node started"
        )

    # COMMAND
    def move(self, command):

        if command not in self.valid_commands:

            self.get_logger().warning(
                f"Rejected invalid command: {command}"
            )

            return False

        with self.command_lock:
            self.current_command = command

        return True

    # SPEED
    def set_speed(self, value):

        try:

            value = float(value)

            self.speed = max(
                self.min_speed,
                min(value, self.max_speed)
            )

            return True

        except (ValueError, TypeError):

            return False

    # PUBLISH MOTOR COMMAND
    def publish_command(self):

        msg = Twist()

        with self.command_lock:

            command = self.current_command

            if command == "forward":

                msg.linear.x = self.speed
                msg.angular.z = 0.0

            elif command == "backward":

                msg.linear.x = -self.speed
                msg.angular.z = 0.0

            elif command == "left":

                msg.linear.x = 0.0
                msg.angular.z = self.turn

            elif command == "right":

                msg.linear.x = 0.0
                msg.angular.z = -self.turn

            else:

                msg.linear.x = 0.0
                msg.angular.z = 0.0

        self.cmd_pub.publish(msg)

        state = String()
        state.data = command

        self.motion_pub.publish(state)

    # ODOMETRY
    def odom_callback(self, msg):

        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y

        self.linear_velocity = (
            msg.twist.twist.linear.x
        )

        self.angular_velocity = (
            msg.twist.twist.angular.z
        )

        self.last_odom_time = time.time()

    # ENCODERS
    def encoder_callback(self, msg):

        if len(msg.data) >= 2:
            self.left_ticks = msg.data[0]
            self.right_ticks = msg.data[1]

            self.last_encoder_time = time.time()

    # LIDAR
    def scan_callback(self, msg):

        self.last_scan_time = time.time()

        valid = []

        for i, distance in enumerate(msg.ranges):

            if not (
                msg.range_min
                < distance
                < msg.range_max
            ):
                continue

            angle = (
                msg.angle_min
                + i * msg.angle_increment
            )

            if abs(angle) <= 0.35:
                valid.append(distance)

        if valid:
            self.front_distance = min(valid)

        else:
            self.front_distance = None

    # IMU
    def imu_callback(self, msg):

        self.last_imu_time = time.time()

    # SENSOR HEALTH
    def alive(self, timestamp, timeout=1.5):

        if timestamp == 0.0:
            return False

        return (
            time.time() - timestamp
        ) < timeout

    # STATUS
    def get_status(self):

        return {

            "command":
                self.current_command,

            "speed":
                round(self.speed, 2),

            "turn_speed":
                round(self.turn, 2),

            "x":
                round(self.x, 3),

            "y":
                round(self.y, 3),

            "linear_velocity":
                round(self.linear_velocity, 3),

            "angular_velocity":
                round(self.angular_velocity, 3),

            "left_ticks":
                self.left_ticks,

            "right_ticks":
                self.right_ticks,

            "front_distance":
                (
                    round(
                        self.front_distance,
                        2
                    )
                    if self.front_distance is not None
                    else None
                ),

            "lidar":
                self.alive(
                    self.last_scan_time
                ),

            "odometry":
                self.alive(
                    self.last_odom_time
                ),

            "imu":
                self.alive(
                    self.last_imu_time
                ),

            "encoders":
                self.alive(
                    self.last_encoder_time
                )
        }


# CAMERA
camera_process = None

def start_camera():

    global camera_process

    try:

        camera_process = subprocess.Popen(

            [
                "rpicam-vid",

                "-t",
                "0",

                "--nopreview",

                "--codec",
                "mjpeg",

                "--width",
                "640",

                "--height",
                "480",

                "--framerate",
                "20",

                "-o",
                "-"
            ],

            stdout=subprocess.PIPE,

            stderr=subprocess.DEVNULL,

            bufsize=0
        )

        print("Camera started")

    except Exception as e:

        camera_process = None

        print(
            f"Camera could not start: {e}"
        )


def camera_frames():

    global camera_process

    buffer = b""

    while True:

        if (
            camera_process is None
            or camera_process.stdout is None
        ):

            time.sleep(0.1)
            continue

        try:

            data = camera_process.stdout.read(
                4096
            )

            if not data:

                time.sleep(0.01)
                continue

            buffer += data

            while True:

                start = buffer.find(
                    b"\xff\xd8"
                )

                if start == -1:
                    break

                end = buffer.find(
                    b"\xff\xd9",
                    start + 2
                )

                if end == -1:
                    break

                frame = buffer[
                    start:end + 2
                ]

                buffer = buffer[
                    end + 2:
                ]

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + frame
                    + b"\r\n"
                )

        except Exception:

            time.sleep(0.1)

# WEB PAGE
PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta name="viewport"
content="width=device-width, initial-scale=1">

<title>Autonomous Delivery Robot</title>

<style>

body {
    background: #202124;
    color: white;
    font-family: Arial, sans-serif;
    text-align: center;
    margin: 0;
    padding: 10px;
}

h1 {
    margin-bottom: 10px;
}

.camera {
    width: 95%;
    max-width: 700px;
    border-radius: 10px;
    border: 2px solid #444;
}

.panel {
    background: #292a2d;
    max-width: 700px;
    margin: 15px auto;
    padding: 15px;
    border-radius: 12px;
}

.status-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
}

.status-box {
    background: #35363a;
    padding: 10px;
    border-radius: 8px;
}

button {
    width: 105px;
    height: 65px;
    margin: 6px;
    font-size: 24px;
    border-radius: 12px;
    border: none;
    cursor: pointer;
    touch-action: manipulation;
}

.move {
    background: #5f6368;
    color: white;
}

.stop {
    background: #d93025;
    color: white;
    font-weight: bold;
}

.speed {
    width: 70px;
    height: 45px;
    font-size: 18px;
}

.good {
    color: #81c995;
}

.bad {
    color: #f28b82;
}

.value {
    font-weight: bold;
}

</style>

</head>


<body>


<h1>Autonomous Delivery Robot</h1>


<img
    class="camera"
    src="/camera"
    alt="Robot Camera"
/>


<div class="panel">

<h2>Robot Status</h2>

<div class="status-grid">

<div class="status-box">
Command:
<span
    class="value"
    id="command">
STOP
</span>
</div>


<div class="status-box">
Speed:
<span
    class="value"
    id="speed">
0.10
</span> m/s
</div>


<div class="status-box">
X:
<span
    class="value"
    id="x">
0
</span> m
</div>


<div class="status-box">
Y:
<span
    class="value"
    id="y">
0
</span> m
</div>


<div class="status-box">
Left encoder:
<span
    class="value"
    id="left_ticks">
0
</span>
</div>


<div class="status-box">
Right encoder:
<span
    class="value"
    id="right_ticks">
0
</span>
</div>


<div class="status-box">
Front obstacle:
<span
    class="value"
    id="front_distance">
--
</span>
</div>


<div class="status-box">
Odometry:
<span id="odom_status">
--
</span>
</div>


<div class="status-box">
LiDAR:
<span id="lidar_status">
--
</span>
</div>


<div class="status-box">
Encoders:
<span id="encoder_status">
--
</span>
</div>


<div class="status-box">
IMU:
<span id="imu_status">
--
</span>
</div>

</div>

</div>


<div class="panel">

<h2>Manual Control</h2>


<div>

<button
    class="move"
    onclick="send('forward')">
⬆
</button>

</div>


<div>

<button
    class="move"
    onclick="send('left')">
⬅
</button>


<button
    class="stop"
    onclick="emergencyStop()">
STOP
</button>


<button
    class="move"
    onclick="send('right')">
➡
</button>

</div>


<div>

<button
    class="move"
    onclick="send('backward')">
⬇
</button>

</div>


<h3>Speed</h3>


<button
    class="speed"
    onclick="changeSpeed(-0.02)">
−
</button>


<span id="speed_display">
0.10
</span> m/s


<button
    class="speed"
    onclick="changeSpeed(0.02)">
+
</button>


<p>
Keyboard:
W/A/S/D or arrow keys.
Space = STOP.
</p>

</div>


<script>

let currentSpeed = 0.10;

// MOVEMENT
function send(cmd) {

    fetch("/move/" + cmd)

        .catch(function(error) {

            console.log(
                "Movement error:",
                error
            );

        });
}

// EMERGENCY STOP
function emergencyStop() {

    send("stop");
}

// KEYBOARD CONTROL
document.addEventListener(
    "keydown",
    function(event) {

        if (event.repeat) {
            return;
        }

        let key =
            event.key.toLowerCase();


        if (
            key === "w" ||
            key === "arrowup"
        ) {

            event.preventDefault();

            send("forward");
        }


        else if (
            key === "s" ||
            key === "arrowdown"
        ) {

            event.preventDefault();

            send("backward");
        }


        else if (
            key === "a" ||
            key === "arrowleft"
        ) {

            event.preventDefault();

            send("left");
        }


        else if (
            key === "d" ||
            key === "arrowright"
        ) {

            event.preventDefault();

            send("right");
        }


        else if (
            key === " "
        ) {

            event.preventDefault();

            emergencyStop();
        }
    }
);

// Stop robot if browser loses focus
window.addEventListener(
    "blur",
    emergencyStop
);


document.addEventListener(
    "visibilitychange",
    function() {

        if (document.hidden) {

            emergencyStop();
        }
    }
);

// SPEED
function changeSpeed(delta) {

    currentSpeed += delta;

    currentSpeed =
        Math.max(
            0.05,
            Math.min(
                currentSpeed,
                0.25
            )
        );

    fetch(
        "/speed/"
        + currentSpeed.toFixed(2)
    );

    document.getElementById(
        "speed_display"
    ).innerText =
        currentSpeed.toFixed(2);
}

// SENSOR HEALTH
function setHealth(id, ok) {

    let element =
        document.getElementById(id);

    if (ok) {

        element.innerText = "ONLINE";
        element.className = "good";

    }

    else {

        element.innerText = "OFFLINE";
        element.className = "bad";

    }
}

// STATUS
function updateStatus() {

    fetch("/status")

    .then(response => response.json())

    .then(data => {

        document.getElementById(
            "command"
        ).innerText =
            data.command.toUpperCase();


        document.getElementById(
            "speed"
        ).innerText =
            Number(data.speed).toFixed(2);


        document.getElementById(
            "speed_display"
        ).innerText =
            Number(data.speed).toFixed(2);


        currentSpeed =
            Number(data.speed);


        document.getElementById(
            "x"
        ).innerText =
            data.x;


        document.getElementById(
            "y"
        ).innerText =
            data.y;


        document.getElementById(
            "left_ticks"
        ).innerText =
            data.left_ticks;


        document.getElementById(
            "right_ticks"
        ).innerText =
            data.right_ticks;


        if (
            data.front_distance === null
        ) {

            document.getElementById(
                "front_distance"
            ).innerText = "--";

        }

        else {

            document.getElementById(
                "front_distance"
            ).innerText =
                data.front_distance
                + " m";
        }


        setHealth(
            "odom_status",
            data.odometry
        );


        setHealth(
            "lidar_status",
            data.lidar
        );


        setHealth(
            "encoder_status",
            data.encoders
        );


        setHealth(
            "imu_status",
            data.imu
        );

    })

    .catch(function(error) {

        console.log(
            "Status error:",
            error
        );

    });
}


setInterval(
    updateStatus,
    500
);


updateStatus();

</script>


</body>

</html>

"""

# GLOBAL ROS NODE
robot = None

# FLASK ROUTES
@app.route("/")
def home():

    return render_template_string(
        PAGE
    )

@app.route("/camera")
def camera():

    return Response(
        camera_frames(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        )
    )

@app.route("/move/<cmd>")
def move(cmd):

    if robot is None:

        return "ROS node unavailable", 503

    if not robot.move(cmd):

        return "Invalid command", 400

    return "OK"

@app.route("/speed/<value>")
def speed(value):

    if robot is None:

        return "ROS node unavailable", 503

    if not robot.set_speed(value):

        return "Invalid speed", 400

    return "OK"

@app.route("/status")
def status():

    if robot is None:

        return jsonify({
            "error": "ROS unavailable"
        }), 503

    return jsonify(
        robot.get_status()
    )

# ROS THREAD
def ros_thread():

    try:

        rclpy.spin(robot)

    except Exception as e:

        print(
            f"ROS thread error: {e}"
        )

# MAIN
def main():

    global robot

    rclpy.init()

    robot = RobotControl()

    thread = threading.Thread(
        target=ros_thread,
        daemon=True
    )

    thread.start()

    time.sleep(1.0)

    start_camera()

    print("")
    print(
        " AUTONOMOUS DELIVERY ROBOT DASHBOARD"
    )
    print("")
    print(
        "Open:"
    )
    print(
        "http://ROBOT_IP:5000"
    )
    print("")

    try:

        app.run(
            host="0.0.0.0",
            port=5000,
            threaded=True,
            use_reloader=False
        )

    finally:
        # STOP ROBOT BEFORE SHUTDOWN
        if robot is not None:

            robot.move("stop")

            for _ in range(3):

                robot.publish_command()

                time.sleep(0.05)

            robot.destroy_node()

        if rclpy.ok():

            rclpy.shutdown()


if __name__ == "__main__":

    main()