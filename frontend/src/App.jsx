import { useEffect, useState } from "react";

import {
    onAuthStateChanged
} from "firebase/auth";

import { auth } from "./services/firebase";

import {
    logoutUser
} from "./services/auth";

import {
    getUserProfile
} from "./services/user";

import Login from "./pages/Login";
import Register from "./pages/Register";

import SenderDashboard
    from "./pages/SenderDashboard";

import ReceiverDashboard
    from "./pages/ReceiverDashboard";

function App() {

    const [user, setUser] = useState(null);

    const [profile, setProfile] =
        useState(null);

    const [page, setPage] =
        useState("login");

    const [loading, setLoading] =
        useState(true);

    //Firebase authentication listener
    useEffect(() => {

        const unsubscribe =
            onAuthStateChanged(
                auth,
                async (currentUser) => {

                    setUser(currentUser);


                    if (currentUser) {

                        const userProfile =
                            await getUserProfile(
                                currentUser.uid
                            );

                        setProfile(
                            userProfile
                        );
                    }

                    else {

                        setProfile(null);
                    }


                    setLoading(false);
                }
            );

        return unsubscribe;

    }, []);

    if (loading) {

        return (
            <div className="loading">
                Loading...
            </div>
        );
    }

    //Logged in
    if (user) {

        const handleLogout =
            async () => {

                await logoutUser();

                setUser(null);
                setProfile(null);
            };


        if (profile?.role === "sender") {

            return (
                <SenderDashboard
                    user={user}
                    profile={profile}
                    onLogout={handleLogout}
                />
            );
        }


        return (
            <ReceiverDashboard
                user={user}
                profile={profile}
                onLogout={handleLogout}
            />
        );
    }

    //Registration page
    if (page === "register") {

        return (
            <>
                <Register
                    onRegister={(newUser) =>
                        setUser(newUser)
                    }
                />

                <div className="switch-auth">

                    <button
                        onClick={() =>
                            setPage("login")
                        }
                    >
                        Already have an account?
                        Login
                    </button>

                </div>
            </>
        );
    }

    //Login page 
    return (
        <>
            <Login
                onLogin={(loggedUser) =>
                    setUser(loggedUser)
                }
            />

            <div className="switch-auth">

                <button
                    onClick={() =>
                        setPage("register")
                    }
                >
                    Create a new account
                </button>

            </div>
        </>
    );
}


export default App;