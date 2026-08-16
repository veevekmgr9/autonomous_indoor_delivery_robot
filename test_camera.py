import subprocess
import cv2
import numpy as np

camera_process = subprocess.Popen(
    [
        "rpicam-vid",
        "-t", "0",
        "--nopreview",
        "--codec", "mjpeg",
        "--width", "640",
        "--height", "480",
        "--framerate", "20",
        "-o", "-"
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    bufsize=0
)

print("Camera started")

buffer = b""

try:
    while True:

        data = camera_process.stdout.read(4096)

        if not data:
            print("Camera stream ended")
            break

        buffer += data

        start = buffer.find(b"\xff\xd8")
        end = buffer.find(b"\xff\xd9")

        if start != -1 and end != -1:

            jpg = buffer[start:end + 2]
            buffer = buffer[end + 2:]

            frame = cv2.imdecode(
                np.frombuffer(jpg, dtype=np.uint8),
                cv2.IMREAD_COLOR
            )

            if frame is None:
                continue

            cv2.imshow("Face Recognition Camera", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

finally:

    camera_process.terminate()
    camera_process.wait()

    cv2.destroyAllWindows()

    print("Camera stopped")
