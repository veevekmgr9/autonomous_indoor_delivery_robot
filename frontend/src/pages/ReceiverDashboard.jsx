import { useEffect, useState } from "react";
import FaceVerification from "../components/FaceVerification";
import FaceRegistration from "../components/FaceRegistration";

import {
    listenToReceiverDeliveries
} from "../services/delivery";


function ReceiverDashboard({
    user,
    profile,
    onLogout
}) {

    const [deliveries, setDeliveries] = useState([]);

    const [verificationDelivery, setVerificationDelivery] =
    useState(null);

    const [showFaceRegistration, setShowFaceRegistration] =
    useState(false);


    /*
     * Listen for receiver deliveries in real time
     */
    useEffect(() => {

        const unsubscribe =
            listenToReceiverDeliveries(
                user.uid,
                setDeliveries
            );

        return unsubscribe;

    }, [user.uid]);


    /*
     * Statistics
     */
    const totalDeliveries =
        deliveries.length;


    const activeDeliveries =
        deliveries.filter(
            delivery =>
                delivery.status !== "COMPLETED"
        ).length;


    const completedDeliveries =
        deliveries.filter(
            delivery =>
                delivery.status === "COMPLETED"
        ).length;


    /*
     * Display friendly status
     */
    const getStatusText = (status) => {

        switch (status) {

            case "PENDING":
                return "Waiting";

            case "ASSIGNED":
                return "Assigned";

            case "OUT_FOR_DELIVERY":
                return "On the way";

            case "ARRIVED":
                return "Arrived";

            case "VERIFYING":
                return "Verification";

            case "VERIFIED":
                return "Verified";

            case "DOOR_OPENED":
                return "Door opened";

            case "COMPLETED":
                return "Completed";

            default:
                return status;
        }
    };


    /*
     * Open verification camera
     */
    const openVerification =
        (delivery) => {

            console.log(
                "Opening verification for:",
                delivery
            );

            setVerificationDelivery(
                delivery
            );
        };


    /*
     * Close verification
     */
    const closeVerification =
        () => {

            setVerificationDelivery(null);
        };


    return (

        <div className="app-layout">

            {/* ================================
                SIDEBAR
            ================================= */}

            <aside className="sidebar">

                <div className="brand">

                    <div className="brand-icon">
                        🤖
                    </div>

                    <div>

                        <h2>
                            AutoDeliver
                        </h2>

                        <span>
                            Robot Delivery
                        </span>

                    </div>

                </div>


                <nav>

                    <div className="nav-item active">
                        <span>▦</span>
                        Dashboard
                    </div>

                    <div className="nav-item">
                        <span>📦</span>
                        My Deliveries
                    </div>

                    <div className="nav-item">
                        <span>🔐</span>
                        Verification
                    </div>

                    <div className="nav-item">
                        <span>⚙</span>
                        Settings
                    </div>

                </nav>


                {/* ROBOT STATUS */}

                <div className="sidebar-bottom">

                    <div className="robot-status">

                        <span className="status-dot"></span>

                        <div>

                            <strong>
                                Robot Online
                            </strong>

                            <small>
                                Delivery system active
                            </small>

                        </div>

                    </div>

                </div>

            </aside>


            {/* ================================
                MAIN CONTENT
            ================================= */}

            <main className="main-content">


                {/* TOP BAR */}

                <header className="topbar">

                    <div>

                        <h1>
                            Dashboard
                        </h1>

                        <p>
                            Manage your incoming
                            robot deliveries
                        </p>

                    </div>


                    <div className="user-area">

                        <div className="user-info">

                            <div className="avatar">

                                {(
                                    profile?.name ||
                                    user.email ||
                                    "U"
                                )[0].toUpperCase()}

                            </div>


                            <div>

                                <strong>
                                    {profile?.name ||
                                        "User"}
                                </strong>

                                <small>
                                    Receiver
                                </small>

                            </div>

                        </div>


                        <button
                            className="logout-button"
                            onClick={onLogout}
                        >
                            Logout
                        </button>

                    </div>

                </header>


                {/* ================================
                    WELCOME
                ================================= */}

                <section className="welcome-section">

                    <div>

                        <h2>
                            Good morning,{" "}
                            {profile?.name ||
                                "there"} 👋
                        </h2>

                        <p>
                            Track your incoming
                            autonomous deliveries
                            in real time.
                        </p>

                    </div>

                </section>
                {!profile?.faceRegistered && (
                <section className="panel security-panel">

                    <div className="security-icon">
                        🔐
                    </div>

                    <div style={{ flex: 1 }}>

                        <h3>
                            Identity Verification
                        </h3>

                        <p>
                            Register your face to securely
                            collect autonomous robot deliveries.
                        </p>

                    </div>

                    <button
                        className="primary-button"
                        onClick={() =>
                            setShowFaceRegistration(true)
                        }
                    >
                        {profile?.faceRegistered
                            ? "Update Face"
                            : "Register Face"
                        }
                    </button>

                </section>
                )}


                {/* ================================
                    STATISTICS
                ================================= */}

                <section className="stats-grid">

                    <div className="stat-card">

                        <div className="stat-icon">
                            📦
                        </div>

                        <div>

                            <span>
                                Total Deliveries
                            </span>

                            <strong>
                                {totalDeliveries}
                            </strong>

                        </div>

                    </div>


                    <div className="stat-card">

                        <div className="stat-icon">
                            🚚
                        </div>

                        <div>

                            <span>
                                Active
                            </span>

                            <strong>
                                {activeDeliveries}
                            </strong>

                        </div>

                    </div>


                    <div className="stat-card">

                        <div className="stat-icon">
                            ✓
                        </div>

                        <div>

                            <span>
                                Completed
                            </span>

                            <strong>
                                {completedDeliveries}
                            </strong>

                        </div>

                    </div>

                </section>


                {/* ================================
                    DELIVERY PANEL
                ================================= */}

                <section className="panel">

                    <div className="panel-header">

                        <div>

                            <h2>
                                Incoming Deliveries
                            </h2>

                            <p>
                                Your deliveries are
                                updated automatically.
                            </p>

                        </div>


                        <span className="panel-icon">
                            📦
                        </span>

                    </div>


                    {deliveries.length === 0 ? (

                        <div className="empty-state">

                            <div>
                                📦
                            </div>

                            <h3>
                                No deliveries yet
                            </h3>

                            <p>
                                When someone sends you
                                an item, it will appear
                                here automatically.
                            </p>

                        </div>

                    ) : (

                        <div className="receiver-delivery-list">

                            {deliveries.map(
                                (delivery) => (

                                    <div
                                        className="receiver-delivery-card"
                                        key={delivery.id}
                                    >

                                        {/* CARD HEADER */}

                                        <div className="receiver-card-header">

                                            <div>

                                                <span className="ticket-number">
                                                    {
                                                        delivery.ticketId
                                                    }
                                                </span>

                                                <h3>
                                                    {
                                                        delivery.item
                                                    }
                                                </h3>

                                            </div>


                                            <span
                                                className={
                                                    `delivery-status status-${delivery.status.toLowerCase()}`
                                                }
                                            >
                                                {
                                                    getStatusText(
                                                        delivery.status
                                                    )
                                                }
                                            </span>

                                        </div>


                                        {/* DELIVERY DETAILS */}

                                        <div className="delivery-details">

                                            <div>

                                                <span>
                                                    FROM
                                                </span>

                                                <strong>
                                                    {
                                                        delivery.senderName
                                                    }
                                                </strong>

                                            </div>


                                            <div>

                                                <span>
                                                    DESTINATION
                                                </span>

                                                <strong>
                                                    {
                                                        delivery.destination
                                                    }
                                                </strong>

                                            </div>


                                            <div>

                                                <span>
                                                    RECEIVER
                                                </span>

                                                <strong>
                                                    {
                                                        delivery.receiverEmail
                                                    }
                                                </strong>

                                            </div>

                                        </div>


                                        {/* ================================
                                            ARRIVED
                                        ================================= */}

                                        {delivery.status ===
                                            "ARRIVED" && (

                                            <div className="arrival-notice">

                                                <div>

                                                    <strong>
                                                        🚚 Your delivery
                                                        has arrived
                                                    </strong>

                                                    <p>
                                                        The robot is
                                                        waiting for
                                                        identity
                                                        verification.
                                                    </p>

                                                </div>


                                                <button
                                                    className="primary-button"
                                                    onClick={() =>
                                                        openVerification(
                                                            delivery
                                                        )
                                                    }
                                                >
                                                    Verify & Open Door →
                                                </button>

                                            </div>

                                        )}


                                        {/* ================================
                                            VERIFYING
                                        ================================= */}

                                        {delivery.status ===
                                            "VERIFYING" && (

                                            <div className="verification-notice">

                                                <span>
                                                    🔐
                                                </span>

                                                <div>

                                                    <strong>
                                                        Identity
                                                        verification
                                                        required
                                                    </strong>

                                                    <p>
                                                        Open your
                                                        camera to
                                                        verify your
                                                        identity.
                                                    </p>

                                                </div>

                                            </div>

                                        )}


                                        {/* ================================
                                            VERIFIED
                                        ================================= */}

                                        {delivery.status ===
                                            "VERIFIED" && (

                                            <div className="verified-notice">

                                                ✓

                                                <div>

                                                    <strong>
                                                        Identity
                                                        verified
                                                    </strong>

                                                    <p>
                                                        Door access
                                                        is being
                                                        authorised.
                                                    </p>

                                                </div>

                                            </div>

                                        )}


                                        {/* ================================
                                            DOOR OPENED
                                        ================================= */}

                                        {delivery.status ===
                                            "DOOR_OPENED" && (

                                            <div className="verified-notice">

                                                🚪

                                                <div>

                                                    <strong>
                                                        Door opened
                                                    </strong>

                                                    <p>
                                                        Please collect
                                                        your delivery.
                                                    </p>

                                                </div>

                                            </div>

                                        )}

                                    </div>

                                )
                            )}

                        </div>

                    )}

                </section>


                {/* ================================
                    SECURITY PANEL
                ================================= */}

                <section className="panel security-panel">

                    <div className="security-icon">
                        🔐
                    </div>


                    <div>

                        <h3>
                            Secure Delivery
                        </h3>

                        <p>
                            Your delivery can only be
                            released after your identity
                            has been verified using your
                            phone camera.
                        </p>

                    </div>

                </section>

            </main>


            {/* ========================================
                FACE VERIFICATION MODAL

                IMPORTANT:
                This MUST be inside the return.
            ========================================= */}

            {verificationDelivery && (

                <FaceVerification

                    delivery={
                        verificationDelivery
                    }

                    onClose={
                        closeVerification
                    }

                    onVerified={() => {

                        console.log(
                            "Test verification completed"
                        );

                        setVerificationDelivery(
                            null
                        );

                    }}

                />

            )}

            {showFaceRegistration && (

                <FaceRegistration

                    user={user}

                    onClose={() =>
                        setShowFaceRegistration(false)
                    }

                    onComplete={() => {

                        setShowFaceRegistration(false);

                        setProfile(prev => ({
                            ...prev,
                            faceRegistered: true
                        }));

                        console.log(
                            "Face registration completed."
                        );

                    }}

                />

            )}

        </div>
    );
}


export default ReceiverDashboard;