import { useEffect, useState } from "react";

import {
    doc,
    updateDoc,
    serverTimestamp,
    collection,
    getDocs,
    query,
    where
} from "firebase/firestore";

import {
    db
} from "../services/firebase";

import {
    createDelivery,
    listenToSenderDeliveries
} from "../services/delivery";

function SenderDashboard({
    user,
    profile,
    onLogout
}) {

    const [deliveries, setDeliveries] = useState([]);

    const [receiverEmail, setReceiverEmail] = useState("");
    const [item, setItem] = useState("");
    const [pickupLocation, setPickupLocation] = useState("");
    const [destination, setDestination] = useState("");

    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);

    const [receiverUsers, setReceiverUsers] = useState([]);

    useEffect(() => {
        const unsubscribe =
            listenToSenderDeliveries(
                user.uid,
                setDeliveries
            );

        return unsubscribe;
    }, [user.uid]);

    useEffect(() => {
        const loadReceivers = async () => {
            try {
                const receiversQuery = query(
                    collection(db, "users"),
                    where("role", "==", "receiver")
                );

                const snapshot = await getDocs(
                    receiversQuery
                );

                const receivers = snapshot.docs.map(
                    (doc) => ({
                        id: doc.id,
                        ...doc.data()
                    })
                );

                setReceiverUsers(receivers);

            } catch (error) {
                console.error(
                    "Error loading receivers:",
                    error
                );
            }
        };

        loadReceivers();
    }, []);


    const handleCreateDelivery = async (e) => {

        e.preventDefault();

        setMessage("");
        setLoading(true);

        try {

            await createDelivery({

                senderId: user.uid,
                senderName:
                    profile?.name || user.email,

                receiverId: receiverEmail,
                receiverEmail,
                item,
                pickupLocation,
                destination
            });


            setReceiverEmail("");
            setItem("");
            setPickupLocation("");
            setDestination("");

            setMessage(
                "Delivery ticket created successfully."
            );

        } catch (error) {

            console.error(error);

            setMessage(
                error.message ||
                "Unable to create delivery."
            );

        } finally {

            setLoading(false);
        }
    };


    const totalDeliveries = deliveries.length;

    const pendingDeliveries =
        deliveries.filter(
            d =>
                d.status === "PENDING" ||
                d.status === "ASSIGNED" ||
                d.status === "OUT_FOR_DELIVERY"
        ).length;

    const completedDeliveries =
        deliveries.filter(
            d => d.status === "COMPLETED"
        ).length;

    const handleStopAndReturnHome = async (delivery) => {
        const confirmed = window.confirm(
            "Stop this delivery and return the robot to HOME?"
        );

        if (!confirmed) {
            return;
        }

        try {
            setMessage("Stopping delivery and returning robot home...");

            // Mark the delivery as cancelled
            await updateDoc(
                doc(db, "deliveries", delivery.id),
                {
                    status: "CANCELLED",
                    cancelledBy: user.uid,
                    cancelledAt: serverTimestamp(),
                    cancellationReason:
                        "Sender requested stop and return home"
                }
            );

            // Command robot to return HOME
            await updateDoc(
                doc(db, "robotState", "current"),
                {
                    status: "RETURN_HOME",
                    activeDeliveryId: delivery.id,
                    ticketId: delivery.ticketId,
                    updatedAt: serverTimestamp()
                }
            );

            setMessage(
                "Delivery stopped. Robot is returning HOME."
            );

        } catch (error) {

            console.error(
                "Stop and return home error:",
                error
            );

            setMessage(
                error.message ||
                "Unable to stop the delivery."
            );
        }
    };
    const handleSendToReceiver = async (delivery) => {

        const confirmed = window.confirm(
            "Package has been picked up. Send the robot to the receiver?"
        );

        if (!confirmed) {
            return;
        }

        try {

            setMessage(
                "Sending robot to receiver..."
            );

            // Update delivery status
            await updateDoc(
                doc(db, "deliveries", delivery.id),
                {
                    status: "SEND_TO_RECEIVER",
                    pickupConfirmed: true,
                    pickupConfirmedAt:
                        serverTimestamp()
                }
            );

            // Command ROS 2 robot
            await updateDoc(
                doc(db, "robotState", "current"),
                {
                    status: "SEND_TO_RECEIVER",
                    activeDeliveryId:
                        delivery.id,
                    ticketId:
                        delivery.ticketId,
                    updatedAt:
                        serverTimestamp()
                }
            );

            setMessage(
                "Robot is now travelling to the receiver."
            );

        } catch (error) {

            console.error(
                "Send to receiver error:",
                error
            );

            setMessage(
                error.message ||
                "Unable to send robot to receiver."
            );
        }
    };

    return (

        <div className="app-layout">

            {/* SIDEBAR */}

            <aside className="sidebar">

                <div className="brand">

                    <div className="brand-icon">
                        🤖
                    </div>

                    <div>
                        <h2>AutoDeliver</h2>
                        <span>Robot Delivery</span>
                    </div>

                </div>


                <nav>

                    <div className="nav-item active">
                        <span>▦</span>
                        Dashboard
                    </div>

                    <div className="nav-item">
                        <span>📦</span>
                        Deliveries
                    </div>

                    <div className="nav-item">
                        <span>＋</span>
                        Create Delivery
                    </div>

                    <div className="nav-item">
                        <span>⚙</span>
                        Settings
                    </div>

                </nav>


                <div className="sidebar-bottom">

                    <div className="robot-status">

                        <span className="status-dot"></span>

                        <div>

                            <strong>
                                Robot Online
                            </strong>

                            <small>
                                Ready for delivery
                            </small>

                        </div>

                    </div>

                </div>

            </aside>


            {/* MAIN */}

            <main className="main-content">

                {/* TOP BAR */}

                <header className="topbar">

                    <div>
                        <h1>Dashboard</h1>

                        <p>
                            Manage your autonomous deliveries
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
                                    Sender
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


                {/* WELCOME */}

                <section className="welcome-section">

                    <div>

                        <h2>
                            Hello,{" "}
                            {profile?.name || "there"} 👋
                        </h2>

                        <p>
                            Here's what's happening
                            with your deliveries.
                        </p>

                    </div>

                </section>


                {/* STATISTICS */}

                <section className="stats-grid">

                    <div className="stat-card">

                        <div className="stat-icon">
                            📦
                        </div>

                        <div>
                            <span>Total Deliveries</span>
                            <strong>
                                {totalDeliveries}
                            </strong>
                        </div>

                    </div>


                    <div className="stat-card">

                        <div className="stat-icon">
                            ⏳
                        </div>

                        <div>
                            <span>Active</span>
                            <strong>
                                {pendingDeliveries}
                            </strong>
                        </div>
                    </div>


                    <div className="stat-card">

                        <div className="stat-icon">
                            ✓
                        </div>

                        <div>
                            <span>Completed</span>
                            <strong>
                                {completedDeliveries}
                            </strong>
                        </div>

                    </div>

                </section>


                {/* CREATE DELIVERY */}

                <section className="panel">

                    <div className="panel-header">

                        <div>

                            <h2>
                                Create New Delivery
                            </h2>

                            <p>
                                Send an item using the
                                autonomous robot.
                            </p>

                        </div>

                        <span className="panel-icon">
                            🚚
                        </span>

                    </div>


                    <form
                        className="delivery-form"
                        onSubmit={
                            handleCreateDelivery
                        }
                    >

                        <div className="form-group">

                            <label>
                                Receiver Email
                            </label>

                            <select
                                value={receiverEmail}
                                onChange={(e) =>
                                    setReceiverEmail(
                                        e.target.value
                                    )
                                }
                                required
                            >
                                <option value="">
                                    Select receiver
                                </option>

                                {receiverUsers.map((receiver) => (
                                    <option
                                        key={receiver.id}
                                        value={
                                            receiver.email
                                        }
                                    >
                                        {receiver.name ? `${receiver.name} (${receiver.email})` : receiver.email}
                                    </option>
                                ))}

                            </select>
                        </div>


                        <div className="form-row">

                            <div className="form-group">

                                <label>
                                    Item
                                </label>

                                <input
                                    type="text"
                                    placeholder="e.g. Laptop"
                                    value={item}
                                    onChange={(e) =>
                                        setItem(
                                            e.target.value
                                        )
                                    }
                                    required
                                />

                            </div>

                            <div className="form-group">

                                <label>
                                    Pickup Location
                                </label>

                                <select
                                    value={pickupLocation}
                                    onChange={(e) =>
                                        setPickupLocation(e.target.value)
                                    }
                                    required
                                >
                                    <option value="">
                                        Select pickup location
                                    </option>

                                    <option value="Room A">
                                        Room A
                                    </option>

                                    <option value="Room B">
                                        Room B
                                    </option>

                                    <option value="HOME">
                                        Home
                                    </option>
                                </select>

                            </div>

                            <div className="form-group">

                                <label>
                                    Receiver Location
                                </label>

                                <select
                                    value={destination}
                                    onChange={(e) =>
                                        setDestination(e.target.value)
                                    }
                                    required
                                >
                                    <option value="">
                                        Select receiver location
                                    </option>

                                    <option value="Room A">
                                        Room A
                                    </option>

                                    <option value="Room B">
                                        Room B
                                    </option>
                                </select>

                            </div>

                        </div>


                        <div className="form-footer">

                            {message && (
                                <span className="success-message">
                                    ✓ {message}
                                </span>
                            )}

                            <button
                                type="submit"
                                className="primary-button"
                                disabled={loading}
                            >
                                {loading
                                    ? "Creating..."
                                    : "Create Delivery →"}
                            </button>

                        </div>

                    </form>

                </section>


                {/* DELIVERIES */}

                <section className="panel">

                    <div className="panel-header">

                        <div>

                            <h2>
                                Recent Deliveries
                            </h2>

                            <p>
                                Track your delivery
                                requests.
                            </p>

                        </div>

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
                                Create your first delivery
                                request above.
                            </p>

                        </div>

                    ) : (

                        <div className="delivery-table">

                            {deliveries.map(
                                (delivery) => (

                                    <div
                                        className="delivery-row"
                                        key={delivery.id}
                                    >

                                        <div className="ticket">

                                            <strong>
                                                {
                                                    delivery.ticketId
                                                }
                                            </strong>

                                            <span>
                                                {
                                                    delivery.item
                                                }
                                            </span>

                                        </div>


                                        <div>

                                            <span className="row-label">
                                                Receiver
                                            </span>

                                            <span>
                                                {
                                                    delivery.receiverEmail
                                                }
                                            </span>

                                        </div>
                                        <div>

                                            <span className="row-label">
                                                Pickup
                                            </span>

                                            <span>
                                                {
                                                    delivery.pickupLocation
                                                }
                                            </span>

                                        </div>

                                        <div>

                                            <span className="row-label">
                                                Destination
                                            </span>

                                            <span>
                                                {
                                                    delivery.destination
                                                }
                                            </span>

                                        </div>


                                        <div>

                                            <span className="status-label">
                                                {delivery.status}
                                            </span>

                                        </div>

                                        <div>
                                            {delivery.status ===
                                                "ARRIVED_AT_PICKUP" && (

                                                    <button
                                                        className="primary-button" style={{ marginRight: "10px" }}
                                                        onClick={() =>
                                                            handleSendToReceiver(delivery)
                                                        }
                                                    >
                                                        Send to Receiver →
                                                    </button>

                                                )}
                                        </div>
                                        <div>
                                            {!["DELIVERED", "CANCELLED", "HOME"].includes(delivery.status) && (
                                                <button
                                                    className="stop-button"
                                                    onClick={() => handleStopAndReturnHome(delivery)}
                                                >
                                                    Stop & Return Home
                                                </button>
                                            )}
                                        </div>

                                    </div>

                                )
                            )}

                        </div>

                    )}

                </section>

            </main>

        </div>
    );
}

export default SenderDashboard;