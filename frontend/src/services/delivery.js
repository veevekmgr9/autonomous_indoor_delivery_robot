import {
    collection,
    addDoc,
    doc,
    getDoc,
    updateDoc,
    serverTimestamp,
    query,
    where,
    onSnapshot,
    getDocs,
    setDoc
} from "firebase/firestore";

import { db } from "./firebase";


// ============================================================
// ROBOT STATE
// ============================================================

const ROBOT_STATE_DOC = doc(
    db,
    "robotState",
    "current"
);


// ============================================================
// FIND USER BY EMAIL
// ============================================================

export async function findUserByEmail(email) {

    const usersRef = collection(
        db,
        "users"
    );

    const q = query(
        usersRef,
        where(
            "email",
            "==",
            email.toLowerCase().trim()
        )
    );

    const snapshot =
        await getDocs(q);

    if (snapshot.empty) {

        return null;
    }

    const userDoc =
        snapshot.docs[0];

    return {
        uid: userDoc.id,
        ...userDoc.data()
    };
}


// ============================================================
// GET CURRENT ROBOT STATE
// ============================================================

export async function getRobotState() {

    const snapshot =
        await getDoc(
            ROBOT_STATE_DOC
        );

    if (!snapshot.exists()) {

        return {
            activeDeliveryId: null,
            ticketId: null,
            status: "IDLE",
            robotId: null
        };
    }

    return snapshot.data();
}


// ============================================================
// CREATE DELIVERY
// ============================================================

export async function createDelivery({
    senderId,
    senderName,
    receiverEmail,
    item,
    destination
}) {

    // --------------------------------------------------------
    // Find receiver
    // --------------------------------------------------------

    const receiver =
        await findUserByEmail(
            receiverEmail
        );


    if (!receiver) {

        throw new Error(
            "No registered user found with this email."
        );
    }


    // --------------------------------------------------------
    // Make sure receiver has correct role
    // --------------------------------------------------------

    if (
        receiver.role !== "receiver"
    ) {

        throw new Error(
            "This user is not registered as a receiver."
        );
    }


    // --------------------------------------------------------
    // Check robot state
    // --------------------------------------------------------

    const robotState =
        await getRobotState();


    if (
        robotState.activeDeliveryId
    ) {

        throw new Error(
            `The robot is currently handling delivery ${
                robotState.ticketId || ""
            }. Please wait until it is completed.`
        );
    }


    // --------------------------------------------------------
    // Generate ticket
    // --------------------------------------------------------

    const ticketId =
        "DLV-" +
        Math.random()
            .toString(36)
            .substring(2, 8)
            .toUpperCase();


    // --------------------------------------------------------
    // Delivery document
    // --------------------------------------------------------

    const delivery = {

        ticketId,

        // Sender
        senderId,
        senderName,

        // Receiver
        receiverId: receiver.uid,
        receiverEmail: receiver.email,

        // Delivery information
        item,
        destination,

        // Robot
        robotId: null,

        // State
        status: "PENDING",

        // Timestamps
        createdAt:
            serverTimestamp(),

        arrivedAt: null,

        verifiedAt: null,

        doorOpenedAt: null,

        completedAt: null
    };


    // --------------------------------------------------------
    // Create delivery
    // --------------------------------------------------------

    const docRef =
        await addDoc(
            collection(
                db,
                "deliveries"
            ),
            delivery
        );


    // --------------------------------------------------------
    // Set robot as busy
    // --------------------------------------------------------

    await setDoc(
        ROBOT_STATE_DOC,
        {
            activeDeliveryId:
                docRef.id,

            ticketId,

            status: "PENDING",

            robotId: null,

            updatedAt:
                serverTimestamp()
        },
        {
            merge: true
        }
    );


    return {
        id: docRef.id,
        ...delivery
    };
}


// ============================================================
// LISTEN TO SENDER ACTIVE DELIVERY
// ============================================================

export function listenToSenderDeliveries(
    senderId,
    callback
) {

    console.log(
        "Sender active delivery listener started"
    );


    const q = query(
        collection(
            db,
            "deliveries"
        ),

        where(
            "senderId",
            "==",
            senderId
        )
    );


    return onSnapshot(

        q,

        async (snapshot) => {

            try {

                const robotState =
                    await getRobotState();


                // No active delivery
                if (
                    !robotState.activeDeliveryId
                ) {

                    callback([]);

                    return;
                }


                const activeDelivery =
                    snapshot.docs
                        .map((doc) => ({
                            id: doc.id,
                            ...doc.data()
                        }))
                        .find(
                            delivery =>
                                delivery.id ===
                                robotState.activeDeliveryId
                        );


                callback(
                    activeDelivery
                        ? [activeDelivery]
                        : []
                );

            } catch (error) {

                console.error(
                    "Error reading robot state:",
                    error
                );

                callback([]);
            }
        },

        (error) => {

            console.error(
                "Sender delivery listener error:",
                error
            );
        }
    );
}


// ============================================================
// LISTEN TO RECEIVER ACTIVE DELIVERY
// ============================================================

export function listenToReceiverDeliveries(
    receiverId,
    callback
) {

    console.log(
        "Receiver active delivery listener started"
    );

    console.log(
        "Receiver UID:",
        receiverId
    );


    const q = query(
        collection(
            db,
            "deliveries"
        ),

        where(
            "receiverId",
            "==",
            receiverId
        )
    );


    return onSnapshot(

        q,

        async (snapshot) => {

            try {

                const robotState =
                    await getRobotState();


                // No active delivery
                if (
                    !robotState.activeDeliveryId
                ) {

                    callback([]);

                    return;
                }


                const activeDelivery =
                    snapshot.docs
                        .map((doc) => ({
                            id: doc.id,
                            ...doc.data()
                        }))
                        .find(
                            delivery =>
                                delivery.id ===
                                robotState.activeDeliveryId
                        );


                callback(
                    activeDelivery
                        ? [activeDelivery]
                        : []
                );

            } catch (error) {

                console.error(
                    "Error reading robot state:",
                    error
                );

                callback([]);
            }
        },

        (error) => {

            console.error(
                "Receiver delivery listener error:",
                error
            );
        }
    );
}


// ============================================================
// UPDATE DELIVERY STATUS
// ============================================================

export async function updateDeliveryStatus(
    deliveryId,
    status
) {

    const deliveryRef =
        doc(
            db,
            "deliveries",
            deliveryId
        );


    const update = {
        status
    };


    // --------------------------------------------------------
    // ARRIVED
    // --------------------------------------------------------

    if (
        status === "ARRIVED"
    ) {

        update.arrivedAt =
            serverTimestamp();
    }


    // --------------------------------------------------------
    // VERIFIED
    // --------------------------------------------------------

    if (
        status === "VERIFIED"
    ) {

        update.verifiedAt =
            serverTimestamp();
    }


    // --------------------------------------------------------
    // DOOR OPENED
    // --------------------------------------------------------

    if (
        status === "DOOR_OPENED"
    ) {

        update.doorOpenedAt =
            serverTimestamp();
    }


    // --------------------------------------------------------
    // COMPLETED
    // --------------------------------------------------------

    if (
        status === "COMPLETED"
    ) {

        update.completedAt =
            serverTimestamp();
    }


    // --------------------------------------------------------
    // Update delivery
    // --------------------------------------------------------

    await updateDoc(
        deliveryRef,
        update
    );


    // --------------------------------------------------------
    // Update robot state
    // --------------------------------------------------------

    if (
        status === "COMPLETED"
    ) {

        // Robot becomes available
        await setDoc(
            ROBOT_STATE_DOC,
            {
                activeDeliveryId: null,
                ticketId: null,
                status: "IDLE",
                robotId: null,
                updatedAt:
                    serverTimestamp()
            },
            {
                merge: true
            }
        );

    } else {

        // Robot continues handling this delivery
        await setDoc(
            ROBOT_STATE_DOC,
            {
                activeDeliveryId:
                    deliveryId,

                status,

                updatedAt:
                    serverTimestamp()
            },
            {
                merge: true
            }
        );
    }
}