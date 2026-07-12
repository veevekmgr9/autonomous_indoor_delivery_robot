#!/usr/bin/env python3

import subprocess
import threading

from flask import Flask, Response, render_template_string

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time


app = Flask(__name__)


# ==========================
# ROS2 CONTROL NODE
# ==========================

class RobotControl(Node):

    def __init__(self):

        super().__init__("phone_dashboard")

        self.publisher = self.create_publisher(
            Twist,
            "/cmd_vel",
            10
        )

        self.speed = 0.20
        self.turn = 0.8


    def move(self, command):

        msg = Twist()

        if command == "forward":
            msg.linear.x = self.speed

        elif command == "backward":
            msg.linear.x = -self.speed

        elif command == "left":
            msg.angular.z = self.turn

        elif command == "right":
            msg.angular.z = -self.turn

        elif command == "stop":
            msg.linear.x = 0.0
            msg.angular.z = 0.0


        self.publisher.publish(msg)



# ==========================
# CAMERA STREAM
# ==========================

camera_process = None


def start_camera():

    global camera_process

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
        stderr=subprocess.DEVNULL

    )

    print("Camera started")



def camera_frames():


    buffer = b""


    while True:


        data = camera_process.stdout.read(4096)


        if not data:
            continue


        buffer += data


        start = buffer.find(b"\xff\xd8")

        end = buffer.find(b"\xff\xd9")


        if start != -1 and end != -1:


            frame = buffer[start:end+2]


            buffer = buffer[end+2:]


            yield (

                b"--frame\r\n"

                b"Content-Type: image/jpeg\r\n\r\n"

                + frame +

                b"\r\n"

            )



# ==========================
# WEB PAGE
# ==========================


PAGE = """

<!DOCTYPE html>

<html>

<head>

<title>Robot Remote</title>


<style>


body{

background:#202124;

color:white;

font-family:Arial;

text-align:center;

}


img{

width:95%;

max-width:700px;

border-radius:10px;

}


button{

width:110px;

height:70px;

margin:8px;

font-size:25px;

border-radius:15px;

}


.stop{

background:red;

color:white;

}


</style>


</head>


<body>


<h1>Delivery Robot Control</h1>


<img src="/camera">


<h2>Movement</h2>


<div>

<button onclick="send('forward')">
⬆
</button>

</div>


<div>

<button onclick="send('left')">
⬅
</button>


<button class="stop" onclick="send('stop')">
STOP
</button>


<button onclick="send('right')">
➡
</button>


</div>


<div>

<button onclick="send('backward')">
⬇
</button>

</div>



<script>


function send(cmd){

fetch("/move/"+cmd);

}


</script>


</body>


</html>

"""



# ==========================
# ROUTES
# ==========================


robot = None



@app.route("/")

def home():

    return render_template_string(PAGE)



@app.route("/camera")

def camera():

    return Response(

        camera_frames(),

        mimetype="multipart/x-mixed-replace; boundary=frame"

    )



@app.route("/move/<cmd>")

def move(cmd):

    robot.move(cmd)

    return "OK"




# ==========================
# MAIN
# ==========================


def ros_thread():

    rclpy.spin(robot)



def main():

    global robot


    rclpy.init()


    robot = RobotControl()


    threading.Thread(

        target=ros_thread,

        daemon=True

    ).start()


    time.sleep(2)
    start_camera()


    print("")
    print("==============================")
    print(" ROBOT DASHBOARD RUNNING")
    print("==============================")
    print("")
    print("Open:")
    print("http://ROBOT_IP:5000")
    print("")



    app.run(

        host="0.0.0.0",

        port=5000,

        threaded=True

    )



if __name__ == "__main__":

    main()