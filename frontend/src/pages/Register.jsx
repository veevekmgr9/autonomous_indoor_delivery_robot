import { useState } from "react";
import { registerUser } from "../services/auth";

function Register({ onRegister }) {

    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [role, setRole] = useState("receiver");

    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);


    const handleRegister = async (e) => {

        e.preventDefault();

        setError("");
        setLoading(true);

        try {

            const user = await registerUser(
                name,
                email,
                password,
                role
            );

            onRegister(user);

        } catch (error) {

            console.error(error);

            if (error.code === "auth/email-already-in-use") {

                setError(
                    "An account with this email already exists."
                );

            } else if (
                error.code === "auth/weak-password"
            ) {

                setError(
                    "Password must be at least 6 characters."
                );

            } else {

                setError(
                    "Registration failed."
                );
            }

        } finally {

            setLoading(false);

        }
    };


    return (
        <div className="auth-container">

            <div className="auth-card">

                <h1></h1>

                <h2>Create Account</h2>

                <form onSubmit={handleRegister}>

                    <input
                        type="text"
                        placeholder="Full name"
                        value={name}
                        onChange={(e) =>
                            setName(e.target.value)
                        }
                        required
                    />

                    <input
                        type="email"
                        placeholder="Email"
                        value={email}
                        onChange={(e) =>
                            setEmail(e.target.value)
                        }
                        required
                    />

                    <input
                        type="password"
                        placeholder="Password"
                        value={password}
                        onChange={(e) =>
                            setPassword(e.target.value)
                        }
                        required
                    />

                    <select
                        value={role}
                        onChange={(e) =>
                            setRole(e.target.value)
                        }
                    >
                        <option value="receiver">
                            Receiver
                        </option>

                        <option value="sender">
                            Sender
                        </option>
                    </select>

                    {error && (
                        <p className="error">
                            {error}
                        </p>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                    >
                        {loading
                            ? "Creating account..."
                            : "Create Account"}
                    </button>

                </form>

            </div>

        </div>
    );
}

export default Register;