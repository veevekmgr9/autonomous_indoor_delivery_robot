import { useState } from "react";
import { loginUser } from "../services/auth";

function Login({ onLogin }) {

    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleLogin = async (e) => {

        e.preventDefault();

        setError("");
        setLoading(true);

        try {

            const user = await loginUser(
                email,
                password
            );

            onLogin(user);

        } catch (error) {

            console.error(error);

            setError(
                "Login failed. Please check your email and password."
            );

        } finally {

            setLoading(false);

        }
    };

    return (
        <div className="auth-container">

            <div className="auth-card">
                <h1 className="app-title">
                    Autonomous Indoor
                    <span>Delivery Robot</span>
                </h1>
                <h2>Login</h2>

                <form onSubmit={handleLogin}>

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
                            ? "Logging in..."
                            : "Login"}
                    </button>

                </form>

            </div>

        </div>
    );
}

export default Login;