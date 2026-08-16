import {
    collection,
    addDoc,
    doc,
    updateDoc,
    serverTimestamp,
    query,
    where,
    orderBy,
    onSnapshot,
    getDocs
} from "firebase/firestore";

import { db } from "./firebase";


/*
 * ============================================
 * FIND USER BY EMAIL
 * ============================================
 */

export async function findUserByEmail(email) {

    const usersRef = collection(db, "users");

    const q = query(
        usersRef,
        where(
            "email",
            "==",
            email.toLowerCase().trim()
        )
    );

    const snapshot = await getDocs(q);

    if (snapshot.empty) {
        return null;
    }

    const userDoc = snapshot.docs[0];

    return {
        uid: userDoc.id,
        ...userDoc.data()
    };
}


/*
 * ============================================
 * CREATE DELIVERY
 * ============================================
 */

export async function createDelivery({
    senderId,
    senderName,
    receiverEmail,
    item,
    destination
}) {

    /*
     * Find receiver using their email
     */
    const receiver =
        await findUserByEmail(receiverEmail);


    /*
     * Receiver does not exist
     */
    if (!receiver) {

        throw new Error(
            "No registered user found with this email."
        );
    }


    /*
     * Make sure receiver has receiver role
     */
    if (receiver.role !== "receiver") {

        throw new Error(
            "This user is not registered as a receiver."
        );
    }


    /*
     * Generate delivery ticket
     */
    const ticketId =
        "DLV-" +
        Math.random()
            .toString(36)
            .substring(2, 8)
            .toUpperCase();


    /*
     * Delivery document
     */
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

        // Current state
        status: "PENDING",

        // Timestamps
        createdAt: serverTimestamp(),

        arrivedAt: null,

        verifiedAt: null,

        doorOpenedAt: null,

        completedAt: null
    };


    /*
     * Save to Firestore
     */
    const docRef = await addDoc(
        collection(db, "deliveries"),
        delivery
    );


    return {
        id: docRef.id,
        ...delivery
    };
}


/*
 * ============================================
 * LISTEN TO SENDER DELIVERIES
 * ============================================
 */

export function listenToSenderDeliveries(
    senderId,
    callback
) {

    const q = query(
        collection(db, "deliveries"),

        where(
            "senderId",
            "==",
            senderId
        ),

        orderBy(
            "createdAt",
            "desc"
        )
    );


    return onSnapshot(

        q,

        (snapshot) => {

            const deliveries =
                snapshot.docs.map(
                    (doc) => ({
                        id: doc.id,
                        ...doc.data()
                    })
                );


            callback(deliveries);
        },

        (error) => {

            console.error(
                "Sender delivery listener error:",
                error
            );
        }
    );
}


/*
 * ============================================
 * LISTEN TO RECEIVER DELIVERIES
 * ============================================
 */
export function listenToReceiverDeliveries(
    receiverId,
    callback
) {

    console.log(
        "Receiver listener started"
    );

    console.log(
        "Receiver UID:",
        receiverId
    );


    const q = query(
        collection(db, "deliveries"),
        where(
            "receiverId",
            "==",
            receiverId
        )
    );


    return onSnapshot(

        q,

        (snapshot) => {

            console.log(
                "Receiver deliveries found:",
                snapshot.size
            );


            const deliveries =
                snapshot.docs.map((doc) => {

                    console.log(
                        "Delivery:",
                        doc.id,
                        doc.data()
                    );

                    return {
                        id: doc.id,
                        ...doc.data()
                    };
                });


            callback(deliveries);
        },

        (error) => {

            console.error(
                "🔥 RECEIVER FIRESTORE ERROR:",
                error
            );

        }
    );
}

/*
 * ============================================
 * UPDATE DELIVERY STATUS
 * ============================================
 */

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


    /*
     * Robot arrived
     */
    if (status === "ARRIVED") {

        update.arrivedAt =
            serverTimestamp();
    }


    /*
     * Receiver verified
     */
    if (status === "VERIFIED") {

        update.verifiedAt =
            serverTimestamp();
    }


    /*
     * Door opened
     */
    if (status === "DOOR_OPENED") {

        update.doorOpenedAt =
            serverTimestamp();
    }


    /*
     * Delivery completed
     */
    if (status === "COMPLETED") {

        update.completedAt =
            serverTimestamp();
    }


    await updateDoc(
        deliveryRef,
        update
    );
}