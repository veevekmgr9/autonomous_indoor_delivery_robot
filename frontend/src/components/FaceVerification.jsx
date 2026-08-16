import { useEffect, useRef, useState } from "react";
import * as faceapi from "face-api.js";
import {
    getRegisteredFaceDescriptor
} from "../services/auth";
import {
    updateDeliveryStatus
} from "../services/auth";

export default function FaceVerification({
    delivery,
    onVerified,
    onClose
}) {

    const videoRef = useRef(null);
    const streamRef = useRef(null);
    const detectionIntervalRef = useRef(null);

    const [cameraStarted, setCameraStarted] =
        useState(false);

    const [modelsLoaded, setModelsLoaded] =
        useState(false);

    const [faceDetected, setFaceDetected] =
        useState(false);

    const [faceConfidence, setFaceConfidence] =
        useState(0);

    const [error, setError] =
        useState("");

    const [message, setMessage] =
        useState(
            "Loading face recognition models..."
        );
    
    const [recognitionResult, setRecognitionResult] =
    useState(null);

    const [recognitionDistance, setRecognitionDistance] =
        useState(null);

    const [recognizing, setRecognizing] =
        useState(false);


    /*
     * =========================================
     * LOAD ALL FACE MODELS
     * =========================================
     */

    async function loadFaceModels() {

        try {

            setError("");

            setMessage(
                "Loading face detection model..."
            );


            /*
             * Tiny Face Detector
             */

            await faceapi.nets.tinyFaceDetector.loadFromUri(
                "/models"
            );

            console.log(
                "✓ Tiny Face Detector loaded"
            );


            /*
             * 68-point facial landmark model
             */

            setMessage(
                "Loading facial landmark model..."
            );

            await faceapi.nets.faceLandmark68Net.loadFromUri(
                "/models"
            );

            console.log(
                "✓ Face Landmark model loaded"
            );


            /*
             * Face recognition model
             */

            setMessage(
                "Loading face recognition model..."
            );

            await faceapi.nets.faceRecognitionNet.loadFromUri(
                "/models"
            );

            console.log(
                "✓ Face Recognition model loaded"
            );


            /*
             * Everything loaded successfully
             */

            setModelsLoaded(true);

            setMessage(
                "All face models loaded. Start the camera."
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
                "Unable to load the face recognition models."
            );

            setMessage(
                "Face model loading failed."
            );
        }
    }


    /*
     * =========================================
     * FACE DETECTION
     * =========================================
     */

    async function detectFace() {

        if (
            !modelsLoaded ||
            !videoRef.current ||
            videoRef.current.readyState < 2
        ) {
            return;
        }


        try {

            const detection =
                await faceapi.detectSingleFace(
                    videoRef.current,
                    new faceapi.TinyFaceDetectorOptions({
                        inputSize: 224,
                        scoreThreshold: 0.5
                    })
                );


            /*
             * FACE FOUND
             */

            if (detection) {

                const confidence =
                    Math.round(
                        detection.score * 100
                    );


                setFaceDetected(true);

                setFaceConfidence(
                    confidence
                );


                setMessage(
                    `Face detected — ${confidence}% confidence`
                );

            }


            /*
             * NO FACE
             */

            else {

                setFaceDetected(false);

                setFaceConfidence(0);

                setMessage(
                    "No face detected. Please position your face inside the frame."
                );
            }

        } catch (err) {

            console.error(
                "Face detection error:",
                err
            );
        }
    }

    /*
     * =========================================
     * FACE RECOGNITION
     * =========================================
     */
    async function recognizeFace() {

        setError("");
        setRecognitionResult(null);
        setRecognitionDistance(null);

        if (!faceDetected) {

            setError(
                "No face detected. Please position your face inside the frame."
            );

            return;
        }

        setRecognizing(true);

        setMessage(
            "Reading your face..."
        );

        try {

            /*
            * Get current receiver's registered
            * face descriptor from Firebase.
            */

            const registeredDescriptor =
                await getRegisteredFaceDescriptor(
                    delivery.receiverId
                );


            /*
            * Generate descriptor from
            * the face currently in the camera.
            */

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

                throw new Error(
                    "Unable to clearly detect your face."
                );
            }


            /*
            * Convert Firebase array to
            * Float32Array.
            */

            const storedDescriptor =
                new Float32Array(
                    registeredDescriptor
                );


            /*
            * Calculate Euclidean distance.
            */

            const distance =
                faceapi.euclideanDistance(
                    result.descriptor,
                    storedDescriptor
                );


            setRecognitionDistance(
                distance
            );


            console.log(
                "Face recognition distance:",
                distance
            );


            /*
            * Initial threshold.
            *
            * We will test this with your
            * actual phone/camera.
            */

            const THRESHOLD = 0.50;


            if (distance <= THRESHOLD) {

                setRecognitionResult(
                    "MATCH"
                );

                setMessage(
                    "Identity verified. Updating delivery..."
                );

                console.log(
                    "✅ FACE MATCH"
                );


                /*
                * Update Firebase delivery status.
                *
                * Robot is NOT involved yet.
                */

                await updateDeliveryStatus(
                    delivery.id,
                    "VERIFIED"
                );


                setMessage(
                    "Identity verified successfully. Delivery authenticated."
                );

                console.log(
                    "DELIVERY VERIFIED"
                );

                stopCamera();
                /*
                * Notify parent dashboard.
                */

                if (onVerified) {
                    onVerified();
                }

                if (onClose) {
                    onClose();
                }

            } else {

                setRecognitionResult(
                    "NO_MATCH"
                );

                setMessage(
                    "Face does not match the registered receiver."
                );

                console.log(
                    "❌ FACE DOES NOT MATCH"
                );
            }

        } catch (err) {

            console.error(
                "Face recognition error:",
                err
            );

            setError(
                err.message ||
                "Face recognition failed."
            );

        } finally {

            setRecognizing(false);
        }
    }


    /*
     * =========================================
     * START CAMERA
     * =========================================
     */

    async function startCamera() {

        setError("");

        try {

            /*
             * Camera access requires HTTPS.
             */

            if (!window.isSecureContext) {

                throw new Error(
                    "Camera requires HTTPS. Please use the secure website address."
                );
            }


            /*
             * Check browser support.
             */

            if (
                !navigator.mediaDevices ||
                !navigator.mediaDevices.getUserMedia
            ) {

                throw new Error(
                    "This browser does not support camera access."
                );
            }


            /*
             * Request front-facing camera.
             */

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


            /*
             * Attach stream to video.
             */

            if (videoRef.current) {

                videoRef.current.srcObject =
                    stream;

                await videoRef.current.play();
            }


            setCameraStarted(true);

            setMessage(
                "Camera started. Position your face inside the frame."
            );


            /*
             * Start face detection.
             *
             * Every 500ms.
             */

            detectionIntervalRef.current =
                setInterval(
                    detectFace,
                    500
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
                    "Camera permission was denied. Please allow camera access in your browser."
                );

            }

            else if (
                err.name ===
                "NotFoundError"
            ) {

                setError(
                    "No camera was found on this device."
                );

            }

            else if (
                err.name ===
                "NotReadableError"
            ) {

                setError(
                    "The camera is already being used by another application."
                );

            }

            else {

                setError(
                    err.message ||
                    "Unable to access the camera."
                );
            }
        }
    }


    /*
     * =========================================
     * STOP CAMERA
     * =========================================
     */

    function stopCamera() {

        /*
         * Stop detection timer.
         */

        if (
            detectionIntervalRef.current
        ) {

            clearInterval(
                detectionIntervalRef.current
            );

            detectionIntervalRef.current =
                null;
        }


        /*
         * Stop camera tracks.
         */

        if (streamRef.current) {

            streamRef.current
                .getTracks()
                .forEach((track) => {

                    track.stop();

                });

            streamRef.current =
                null;
        }


        /*
         * Clear video.
         */

        if (videoRef.current) {

            videoRef.current.srcObject =
                null;
        }


        setCameraStarted(false);

        setFaceDetected(false);

        setFaceConfidence(0);

        setMessage(
            "Camera stopped."
        );
    }


    /*
     * =========================================
     * CLOSE VERIFICATION
     * =========================================
     */

    function handleClose() {

        stopCamera();

        if (onClose) {

            onClose();

        }
    }


    /*
     * =========================================
     * TEMPORARY TEST
     *
     * This ONLY tests face detection.
     *
     * It does NOT authenticate the user.
     * =========================================
     */

    function handleTestVerification() {

        setError("");


        /*
         * No face
         */

        if (!faceDetected) {

            setError(
                "No face detected. Please position your face inside the frame."
            );

            return;
        }


        /*
         * Face detected
         */

        setMessage(
            `Face detection successful — ${faceConfidence}% confidence.`
        );


        console.log(
            "Face detection test successful."
        );

        console.log(
            "Delivery:",
            delivery
        );


        /*
         * IMPORTANT:
         *
         * We intentionally do NOT call
         * onVerified() yet.
         *
         * A detected face does NOT mean
         * the person is authorised.
         *
         * Actual recognition will be
         * implemented next.
         */
    }


    /*
     * =========================================
     * LOAD MODELS WHEN COMPONENT OPENS
     * =========================================
     */

    useEffect(() => {

        loadFaceModels();


        /*
         * Cleanup when component closes.
         */

        return () => {


            /*
             * Stop detection timer.
             */

            if (
                detectionIntervalRef.current
            ) {

                clearInterval(
                    detectionIntervalRef.current
                );

                detectionIntervalRef.current =
                    null;
            }


            /*
             * Stop camera.
             */

            if (streamRef.current) {

                streamRef.current
                    .getTracks()
                    .forEach((track) => {

                        track.stop();

                    });

                streamRef.current =
                    null;
            }

        };

    }, []);


    /*
     * =========================================
     * USER INTERFACE
     * =========================================
     */

    return (

        <div className="verification-overlay">

            <div className="verification-card">


                {/* ================================
                    HEADER
                ================================= */}

                <div className="verification-header">

                    <div>

                        <h2>
                            Verify Your Identity
                        </h2>

                        <p>
                            Delivery #
                            {delivery?.ticketId}
                        </p>

                    </div>


                    <button
                        className="close-button"
                        onClick={handleClose}
                    >
                        ×
                    </button>

                </div>


                {/* ================================
                    CONTENT
                ================================= */}

                <div className="verification-content">


                    {/* ================================
                        CAMERA AREA
                    ================================= */}

                    <div className="camera-container">


                        {/* CAMERA NOT STARTED */}

                        {!cameraStarted && (

                            <div className="camera-placeholder">

                                <div className="camera-icon">
                                    📷
                                </div>


                                <h3>
                                    Face Verification
                                </h3>


                                <p>
                                    Your phone camera
                                    will be used to
                                    verify your identity.
                                </p>


                                {!modelsLoaded && (

                                    <p>
                                        Loading face
                                        recognition
                                        models...
                                    </p>

                                )}


                                <button
                                    className="primary-button"
                                    onClick={
                                        startCamera
                                    }
                                    disabled={
                                        !modelsLoaded
                                    }
                                >

                                    {modelsLoaded
                                        ? "Start Camera"
                                        : "Loading Models..."
                                    }

                                </button>

                            </div>

                        )}


                        {/* LIVE CAMERA */}

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


                        {/* FACE FRAME */}

                        {cameraStarted && (

                            <div
                                className={
                                    faceDetected
                                        ? "face-frame face-detected"
                                        : "face-frame"
                                }
                            >

                                <div
                                    className="face-corner top-left"
                                />

                                <div
                                    className="face-corner top-right"
                                />

                                <div
                                    className="face-corner bottom-left"
                                />

                                <div
                                    className="face-corner bottom-right"
                                />

                            </div>

                        )}


                        {/* FACE STATUS */}

                        {cameraStarted && (

                            <div className="face-status">

                                {faceDetected
                                    ? `✅ Face detected ${faceConfidence}%`
                                    : "🔍 Looking for face..."
                                }

                            </div>

                        )}

                    </div>


                    {/* ================================
                        ERROR
                    ================================= */}

                    {error && (

                        <div className="error-message">

                            ⚠️ {error}

                        </div>

                    )}


                    {/* ================================
                        STATUS MESSAGE
                    ================================= */}

                    <div className="verification-message">
                        {recognitionResult === "MATCH" && (

                            <div className="recognition-success">

                                <div className="recognition-icon">
                                    ✓
                                </div>

                                <h3>
                                    Identity Verified
                                </h3>

                                <p>
                                    Your face matches the registered receiver.
                                </p>

                                {recognitionDistance !== null && (
                                    <small>
                                        Face distance:{" "}
                                        {recognitionDistance.toFixed(4)}
                                    </small>
                                )}

                            </div>

                        )}

                        {recognitionResult === "NO_MATCH" && (

                            <div className="recognition-failed">

                                <div className="recognition-icon">
                                    ✕
                                </div>

                                <h3>
                                    Identity Not Verified
                                </h3>

                                <p>
                                    The detected face does not match
                                    the registered receiver.
                                </p>

                                {recognitionDistance !== null && (
                                    <small>
                                        Face distance:{" "}
                                        {recognitionDistance.toFixed(4)}
                                    </small>
                                )}

                            </div>

                        )}

                        {faceDetected && (
                            <span>
                                ✅{" "}
                            </span>
                        )}

                        {message}

                    </div>


                    {/* ================================
                        ACTION BUTTONS
                    ================================= */}

                    {cameraStarted && (

                        <div className="verification-actions">


                            {/* STOP CAMERA */}

                            <button
                                className="secondary-button"
                                onClick={
                                    stopCamera
                                }
                            >
                                Stop Camera
                            </button>


                            {/* TEST FACE */}

                            <button
                                className="primary-button"
                                onClick={
                                    recognizeFace
                                }
                                disabled={
                                    !faceDetected || recognizing
                                }
                            >
                                {recognizing
                                    ? "Recognizing..."
                                    : "Verify Identity"
                                }
                            </button>

                        </div>

                    )}

                </div>

            </div>

        </div>
    );
}