import subprocess
import cv2
import numpy as np
import insightface
import time


# ============================================================
# INSIGHTFACE
# ============================================================

app = insightface.app.FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

app.prepare(
    ctx_id=-1,
    det_size=(320, 320)
)

print("InsightFace ready")


# ============================================================
# CAMERA
# ============================================================

camera_process = subprocess.Popen(
    [
        "rpicam-vid",
        "-t", "0",
        "--nopreview",
        "--codec", "mjpeg",
        "--width", "640",
        "--height", "480",
        "--framerate", "15",
        "-o", "-"
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    bufsize=0
)

print("Camera started")


buffer = b""

frame_count = 0
last_detection_time = 0

faces = []


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

            frame_count += 1

            # ====================================================
            # ONLY RUN FACE AI EVERY 10 FRAMES
            # ====================================================

            if frame_count % 10 == 0:

                now = time.time()

                # Don't run AI more than once per second
                if now - last_detection_time >= 1.0:

                    last_detection_time = now

                    faces = app.get(frame)

                    print(
                        f"Faces detected: {len(faces)}"
                    )


            # ====================================================
            # DRAW LAST DETECTION
            # ====================================================

            for face in faces:

                x1, y1, x2, y2 = face.bbox.astype(int)

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    "Face detected",
                    (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )


            cv2.imshow(
                "Light Face Detection",
                frame
            )


            if cv2.waitKey(1) & 0xFF == ord("q"):
                break


finally:

    camera_process.terminate()
    camera_process.wait()

    cv2.destroyAllWindows()

    print("Camera stopped")
