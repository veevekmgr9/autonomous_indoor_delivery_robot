import {
    doc,
    getDoc
} from "firebase/firestore";

import { db } from "./firebase";


export async function getUserProfile(
    userId
) {

    const userRef =
        doc(db, "users", userId);

    const snapshot =
        await getDoc(userRef);


    if (!snapshot.exists()) {
        return null;
    }


    return snapshot.data();
}