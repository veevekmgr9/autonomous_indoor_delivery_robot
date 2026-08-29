import {
    useEffect,
    useRef,
    useState
} from "react";

import * as faceapi from "face-api.js";

import {
    saveFaceDescriptor
} from "../services/auth";

export default function FaceRegistration({
    user,
    onComplete,
    onClose
}) {

    const videoRef =
        useRef(null);

    const streamRef =
        useRef(null);

    const [cameraStarted, setCameraStarted] =
        useState(false);

    const [modelsLoaded, setModelsLoaded] =
        useState(false);

    const [faceDetected, setFaceDetected] =
        useState(false);

    const [samples, setSamples] =
        useState([]);

    const [capturing, setCapturing] =
        useState(false);

    const [error, setError] =
        useState("");

    const [message, setMessage] =
        useState(
            "Loading face recognition models..."
        );

    //LOAD MODELS
    async function loadModels() {
        try {

            setMessage(
                "Loading face detection model..."
            );

            await faceapi.nets.tinyFaceDetector.loadFromUri(
                "/models"
            );

            console.log(
                "✓ Tiny Face Detector loaded"
            );

            setMessage(
                "Loading facial landmark model..."
            );

            await faceapi.nets.faceLandmark68Net.loadFromUri(
                "/models"
            );

            console.log(
                "✓ Face Landmark model loaded"
            );

            setMessage(
                "Loading face recognition model..."
            );

            await faceapi.nets.faceRecognitionNet.loadFromUri(
                "/models"
            );

            console.log(
                "✓ Face Recognition model loaded"
            );

            setModelsLoaded(true);

            setMessage(
                "Models ready. Start the camera."
            );

            console.log(
                "✓ ALL FACE MODELS LOADED"
            );

        } catch (err) {

            console.error(
                "Face model loading error:",
                err
            );

            setError(
                "Unable to load face recognition models."
            );

            setMessage(
                "Face model loading failed."
            );
        }
    }

    //START CAMERA
    async function startCamera() {

        setError("");

        try {

            if (!window.isSecureContext) {

                throw new Error(
                    "Camera requires HTTPS."
                );
            }

            if (
                !navigator.mediaDevices ||
                !navigator.mediaDevices.getUserMedia
            ) {

                throw new Error(
                    "Camera access is not supported."
                );
            }

            const stream =
                await navigator.mediaDevices.getUserMedia({

                    video: {

                        facingMode: "user",

                        width: {
                            ideal: 1280
                        },

                        height: {
                            ideal: 720
                        }

                    },

                    audio: false

                });

            streamRef.current =
                stream;

            if (videoRef.current) {

                videoRef.current.srcObject =
                    stream;

                await videoRef.current.play();
            }

            setCameraStarted(true);

            setMessage(
                "Camera started. Position your face inside the frame."
            );

        } catch (err) {

            console.error(
                "Camera error:",
                err
            );

            if (
                err.name ===
                "NotAllowedError"
            ) {

                setError(
                    "Camera permission was denied."
                );

            } else if (
                err.name ===
                "NotFoundError"
            ) {

                setError(
                    "No camera was found."
                );

            } else {

                setError(
                    err.message ||
                    "Unable to access camera."
                );
            }
        }
    }

    //GET FACE DESCRIPTOR
    async function getFaceDescriptor() {

        if (
            !videoRef.current ||
            videoRef.current.readyState < 2
        ) {

            return null;
        }

        const result =
            await faceapi
                .detectSingleFace(
                    videoRef.current,
                    new faceapi.TinyFaceDetectorOptions({
                        inputSize: 224,
                        scoreThreshold: 0.5
                    })
                )
                .withFaceLandmarks()
                .withFaceDescriptor();

        if (!result) {

            return null;
        }

        return Array.from(
            result.descriptor
        );
    }

    //CHECK FACE
    async function checkFace() {

        if (
            !cameraStarted ||
            capturing
        ) {

            return;
        }

        try {

            const descriptor =
                await getFaceDescriptor();

            if (descriptor) {

                setFaceDetected(true);

                setMessage(
                    "Face detected. Keep your head still."
                );

            } else {

                setFaceDetected(false);

                setMessage(
                    "No face detected. Position your face inside the frame."
                );
            }
        } catch (err) {

            console.error(
                "Face detection error:",
                err
            );
        }
    }

    //CAPTURE ONE SAMPLE
    async function captureSample() {

        const descriptor =
            await getFaceDescriptor();

        if (!descriptor) {

            setError(
                "No clear face detected. Please look directly at the camera."
            );

            return null;
        }


        return descriptor;
    }

    //CAPTURE 5 SAMPLES
    async function registerFace() {
        setError("");

        setCapturing(true);

        setMessage(
            "Preparing face registration..."
        );

        const capturedSamples = [];

        try {

            for (
                let i = 0;
                i < 5;
                i++
            ) {

                setMessage(
                    `Look directly at the camera. Capturing sample ${i + 1} of 5...`
                );

                await new Promise(
                    resolve =>
                        setTimeout(
                            resolve,
                            800
                        )
                );

                const descriptor =
                    await captureSample();

                if (!descriptor) {

                    throw new Error(
                        `Unable to capture sample ${i + 1}. Please keep your face clearly visible.`
                    );
                }

                capturedSamples.push(
                    descriptor
                );

                setSamples([
                    ...capturedSamples
                ]);
            }

            setMessage(
                "Processing face data..."
            );

            const descriptorLength =
                capturedSamples[0].length;


            const averageDescriptor =
                new Array(
                    descriptorLength
                ).fill(0);

            for (
                const descriptor
                of capturedSamples
            ) {

                for (
                    let i = 0;
                    i < descriptorLength;
                    i++
                ) {

                    averageDescriptor[i] +=
                        descriptor[i];
                }
            }

            for (
                let i = 0;
                i < descriptorLength;
                i++
            ) {

                averageDescriptor[i] /=
                    capturedSamples.length;
            }

            //Save to Firebase.
            setMessage(
                "Saving your face registration..."
            );

            await saveFaceDescriptor(
                user.uid,
                averageDescriptor
            );

            setMessage(
                "Face registration completed successfully."
            );

            console.log(
                "Face registration successful."
            );

            if (onComplete) {

                onComplete();
            }

        } catch (err) {

            console.error(
                "Face registration error:",
                err
            );

            setError(
                err.message ||
                "Face registration failed."
            );

            setMessage(
                "Face registration failed."
            );

        } finally {
            setCapturing(false);
        }
    }

    //STOP CAMERA
    function stopCamera() {

        if (streamRef.current) {

            streamRef.current
                .getTracks()
                .forEach(track => {

                    track.stop();

                });

            streamRef.current =
                null;
        }

        if (videoRef.current) {

            videoRef.current.srcObject =
                null;
        }

        setCameraStarted(false);

        setFaceDetected(false);
    }

    //CLOSE
    function handleClose() {
        if (capturing) {

            return;
        }

        stopCamera();

        if (onClose) {

            onClose();
        }
    }

    //LOAD MODELS
    useEffect(() => {

        loadModels();

        return () => {

            if (streamRef.current) {

                streamRef.current
                    .getTracks()
                    .forEach(track => {

                        track.stop();

                    });
            }
        };
    }, []);

    //FACE CHECK TIMER
    useEffect(() => {

        if (!cameraStarted) {

            return;
        }

        const interval =
            setInterval(
                checkFace,
                500
            );

        return () => {

            clearInterval(
                interval
            );

        };

    }, [
        cameraStarted,
        capturing
    ]);

    //UI
    return (

        <div className="verification-overlay">

            <div className="verification-card">

                {/* HEADER */}

                <div className="verification-header">

                    <div>

                        <h2>
                            Register Your Face
                        </h2>

                        <p>
                            Secure delivery
                            authentication
                        </p>

                    </div>

                    <button
                        className="close-button"
                        onClick={handleClose}
                        disabled={capturing}
                    >
                        ×
                    </button>
                </div>

                {/* CONTENT */}
                <div className="verification-content">

                    {/* CAMERA */}
                    <div className="camera-container">

                        {!cameraStarted && (

                            <div className="camera-placeholder">

                                <div className="camera-icon">
                                    🔐
                                </div>

                                <h3>
                                    Face Registration
                                </h3>

                                <p>
                                    We will capture
                                    several face samples
                                    to create your
                                    authentication
                                    profile.
                                </p>

                                {!modelsLoaded && (

                                    <p>
                                        Loading face
                                        models...
                                    </p>

                                )}

                                <button
                                    className="primary-button"
                                    onClick={
                                        startCamera
                                    }
                                    disabled={
                                        !modelsLoaded ||
                                        capturing
                                    }
                                >

                                    {modelsLoaded
                                        ? "Start Camera"
                                        : "Loading Models..."
                                    }

                                </button>
                            </div>
                        )}

                        <video
                            ref={videoRef}
                            className={
                                cameraStarted
                                    ? "camera-video"
                                    : "camera-video hidden"
                            }
                            autoPlay
                            playsInline
                            muted
                        />

                        {cameraStarted && (

                            <div
                                className={
                                    faceDetected
                                        ? "face-frame face-detected"
                                        : "face-frame"
                                }
                            >
                                <div className="face-corner top-left" />
                                <div className="face-corner top-right" />
                                <div className="face-corner bottom-left" />
                                <div className="face-corner bottom-right" />
                            </div>
                        )}
                    </div>

                    {/* ERROR */}

                    {error && (

                        <div className="error-message">

                            ⚠️ {error}

                        </div>

                    )}

                    {/* STATUS */}
                    <div className="verification-message">

                        {faceDetected && (
                            <span>
                                ✅{" "}
                            </span>
                        )}

                        {message}

                    </div>

                    {/* SAMPLE COUNTER */}
                    {cameraStarted && (

                        <div className="sample-progress">

                            <strong>
                                Face Samples
                            </strong>

                            <div className="sample-dots">

                                {[0, 1, 2, 3, 4].map(
                                    index => (

                                        <span
                                            key={index}
                                            className={
                                                index <
                                                    samples.length
                                                    ? "sample-dot complete"
                                                    : "sample-dot"
                                            }
                                        >
                                            {index <
                                                samples.length
                                                ? "✓"
                                                : index + 1}
                                        </span>

                                    )
                                )}

                            </div>

                        </div>
                    )}


                    {/* ACTIONS */}
                    {cameraStarted && (

                        <div className="verification-actions">

                            <button
                                className="secondary-button"
                                onClick={
                                    stopCamera
                                }
                                disabled={
                                    capturing
                                }
                            >
                                Stop Camera
                            </button>

                            <button
                                className="primary-button"
                                onClick={
                                    registerFace
                                }
                                disabled={
                                    !faceDetected ||
                                    capturing
                                }
                            >

                                {capturing
                                    ? "Registering..."
                                    : "Register My Face"
                                }

                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}