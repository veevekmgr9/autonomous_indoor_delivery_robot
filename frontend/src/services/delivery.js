import {
    collection,
    addDoc,
    doc,
    getDoc,
    updateDoc,
    setDoc,
    serverTimestamp,
    query,
    where,
    orderBy,
    onSnapshot,
    getDocs
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
    destination,
    pickupLocation
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
        pickupLocation,

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

    const deliveryRef = doc(
        db,
        "deliveries",
        deliveryId
    );

    const update = {
        status
    };

    if (status === "ARRIVED") {
        update.arrivedAt = serverTimestamp();
    }

    if (status === "VERIFIED") {
        update.verifiedAt = serverTimestamp();
    }

    if (status === "DOOR_OPENED") {
        update.doorOpenedAt = serverTimestamp();
    }

    if (status === "COMPLETED") {
        update.completedAt = serverTimestamp();
    }

    // Update delivery document
    await updateDoc(
        deliveryRef,
        update
    );


    // =================================================
    // KEEP ROBOT STATE SYNCHRONISED
    // =================================================

    if (
        status === "VERIFIED"
    ) {

        const deliverySnapshot =
            await getDoc(
                deliveryRef
            );

        if (
            deliverySnapshot.exists()
        ) {

            const delivery =
                deliverySnapshot.data();

            await setDoc(
                doc(
                    db,
                    "robotState",
                    "current"
                ),
                {
                    activeDeliveryId:
                        deliveryId,

                    ticketId:
                        delivery.ticketId,

                    status:
                        "VERIFIED",

                    updatedAt:
                        serverTimestamp()
                },
                {
                    merge: true
                }
            );

            console.log(
                `🤖 Robot state updated: ${delivery.ticketId} → VERIFIED`
            );
        }
    }
}