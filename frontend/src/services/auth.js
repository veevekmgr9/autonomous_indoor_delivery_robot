import {
    createUserWithEmailAndPassword,
    signInWithEmailAndPassword,
    signOut
} from "firebase/auth";

import {
    doc,
    setDoc,
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


export async function logoutUser() {
    await signOut(auth);
}