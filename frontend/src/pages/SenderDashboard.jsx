import { useEffect, useState } from "react";

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
    const [destination, setDestination] = useState("");

    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);


    useEffect(() => {

        const unsubscribe =
            listenToSenderDeliveries(
                user.uid,
                setDeliveries
            );

        return unsubscribe;

    }, [user.uid]);


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

                destination
            });


            setReceiverEmail("");
            setItem("");
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
                            Good morning,{" "}
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

                            <input
                                type="email"
                                placeholder="receiver@example.com"
                                value={receiverEmail}
                                onChange={(e) =>
                                    setReceiverEmail(
                                        e.target.value
                                    )
                                }
                                required
                            />

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
                                Destination
                            </label>

                            <select
                                value={destination}
                                onChange={(e) =>
                                    setDestination(e.target.value)
                                }
                                required
                            >
                                <option value="">
                                    Select destination
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