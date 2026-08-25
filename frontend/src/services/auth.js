import {
    createUserWithEmailAndPassword,
    signInWithEmailAndPassword,
    signOut
} from "firebase/auth";

import {
    doc,
    getDoc,
    setDoc,
    updateDoc,
    serverTimestamp
} from "firebase/firestore";

import { auth, db } from "./firebase";


export async function registerUser(
    name,
    email,
    password,
    role
) {
    const userCredential =
        await createUserWithEmailAndPassword(
            auth,
            email,
            password
        );

    const user = userCredential.user;

    await setDoc(
        doc(db, "users", user.uid),
        {
            name: name,
            email: email,
            role: role,
            faceRegistered: false,
            createdAt: serverTimestamp()
        }
    );

    return user;
}


export async function loginUser(
    email,
    password
) {
    const userCredential =
        await signInWithEmailAndPassword(
            auth,
            email,
            password
        );

    return userCredential.user;
}

export async function saveFaceDescriptor(
    userId,
    descriptor
) {

    const userRef = doc(
        db,
        "users",
        userId
    );

    await updateDoc(
        userRef,
        {
            faceRegistered: true,
            faceDescriptor: descriptor
        }
    );

    console.log(
        "Face descriptor saved successfully."
    );
}

export async function getRegisteredFaceDescriptor(userId) {

    const userRef = doc(
        db,
        "users",
        userId
    );

    const snapshot = await getDoc(userRef);

    if (!snapshot.exists()) {
        throw new Error(
            "User profile not found."
        );
    }

    const data = snapshot.data();

    if (
        !data.faceRegistered ||
        !data.faceDescriptor
    ) {
        throw new Error(
            "No registered face found for this user."
        );
    }

    return data.faceDescriptor;
}

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


    // ================================================
    // UPDATE DELIVERY
    // ================================================

    await updateDoc(
        deliveryRef,
        update
    );


    // ================================================
    // UPDATE ROBOT STATE
    // ================================================

    if (status === "VERIFIED") {

        const deliverySnapshot =
            await getDoc(
                deliveryRef
            );

        if (!deliverySnapshot.exists()) {

            throw new Error(
                "Delivery document not found."
            );
        }

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

export async function reportAuthenticationFailure(
    deliveryId
) {
    const deliveryRef = doc(
        db,
        "deliveries",
        deliveryId
    );

    await updateDoc(
        deliveryRef,
        {
            authenticationAttemptAt:
                Date.now()
        }
    );
}


export async function logoutUser() {
    await signOut(auth);
}