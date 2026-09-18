import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Check,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  Moon,
  Sparkles,
  Sun,
  UserRound,
} from "lucide-react";
import toast from "react-hot-toast";
import { useAuth } from "../context/useAuth";
import "../styles/Register.css";

export default function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem("autodev_login_theme");

    if (savedTheme === "light" || savedTheme === "dark") {
      return savedTheme;
    }

    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  });

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("autodev_login_theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((currentTheme) =>
      currentTheme === "dark" ? "light" : "dark"
    );
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!username.trim() || !email.trim() || !password || !confirmPassword) {
      toast.error("Please fill in all fields.");
      return;
    }

    if (password.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }

    if (password !== confirmPassword) {
      toast.error("Passwords do not match.");
      return;
    }

    try {
      setLoading(true);

      await register(
        username.trim(),
        email.trim(),
        password,
      );

      toast.success("Account created successfully.");
      navigate("/login", { replace: true });
    } catch (error) {
      const message =
        error?.response?.data?.detail ||
        "Unable to create your account.";

      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const isDark = theme === "dark";

  return (
    <main className="register-page">
      <section className="register-shell">
        <div className="register-brand-panel">
          <div className="register-brand">
            <div className="register-brand-mark">A</div>
            <span className="register-brand-name">AutoDev AI</span>
          </div>

          <div className="register-brand-content">
            <p className="register-eyebrow">
              Start building today
            </p>

            <h1>
              Build ideas.
              <br />
              Ship software.
            </h1>

            <p>
              Create your AutoDev AI account and turn your ideas into working
              software with an autonomous development workflow.
            </p>

            <div className="register-feature-list">
              <div className="register-feature">
                <span className="register-feature-icon">
                  <Sparkles size={15} />
                </span>
                AI-powered development workflow
              </div>

              <div className="register-feature">
                <span className="register-feature-icon">
                  <Check size={15} />
                </span>
                Automated testing and validation
              </div>

              <div className="register-feature">
                <span className="register-feature-icon">
                  <Check size={15} />
                </span>
                Build and iterate from a simple prompt
              </div>
            </div>
          </div>

          <span className="register-brand-footer">
            Your next project starts here.
          </span>
        </div>

        <div className="register-form-panel">
          <button
            type="button"
            className="register-theme-toggle"
            onClick={toggleTheme}
            aria-label={
              isDark ? "Switch to light theme" : "Switch to dark theme"
            }
            title={isDark ? "Light theme" : "Dark theme"}
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          <div className="register-form-container">
            <div className="register-form-header">
              <h2>Create your account</h2>
              <p>
                Set up your account and start building with AutoDev AI.
              </p>
            </div>

            <form className="register-form" onSubmit={handleSubmit}>
              <div className="register-field">
                <label htmlFor="register-username">Username</label>

                <div className="register-input-wrapper">
                  <UserRound className="register-input-icon" />

                  <input
                    id="register-username"
                    name="username"
                    type="text"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder="Choose a username"
                    className="register-input"
                    autoComplete="username"
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="register-field">
                <label htmlFor="register-email">Email</label>

                <div className="register-input-wrapper">
                  <Mail className="register-input-icon" />

                  <input
                    id="register-email"
                    name="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    className="register-input"
                    autoComplete="email"
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="register-field">
                <label htmlFor="register-password">Password</label>

                <div className="register-input-wrapper">
                  <LockKeyhole className="register-input-icon" />

                  <input
                    id="register-password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="At least 8 characters"
                    className="register-input"
                    autoComplete="new-password"
                    disabled={loading}
                  />

                  <button
                    type="button"
                    className="register-password-toggle"
                    onClick={() => setShowPassword((value) => !value)}
                    aria-label={
                      showPassword ? "Hide password" : "Show password"
                    }
                    title={showPassword ? "Hide password" : "Show password"}
                    disabled={loading}
                  >
                    {showPassword ? (
                      <EyeOff size={17} />
                    ) : (
                      <Eye size={17} />
                    )}
                  </button>
                </div>
              </div>

              <div className="register-field">
                <label htmlFor="confirm-password">Confirm Password</label>

                <div className="register-input-wrapper">
                  <LockKeyhole className="register-input-icon" />

                  <input
                    id="confirm-password"
                    name="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(event) =>
                      setConfirmPassword(event.target.value)
                    }
                    placeholder="Re-enter your password"
                    className="register-input"
                    autoComplete="new-password"
                    disabled={loading}
                  />

                  <button
                    type="button"
                    className="register-password-toggle"
                    onClick={() =>
                      setShowConfirmPassword((value) => !value)
                    }
                    aria-label={
                      showConfirmPassword
                        ? "Hide password"
                        : "Show password"
                    }
                    title={
                      showConfirmPassword
                        ? "Hide password"
                        : "Show password"
                    }
                    disabled={loading}
                  >
                    {showConfirmPassword ? (
                      <EyeOff size={17} />
                    ) : (
                      <Eye size={17} />
                    )}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                className="register-submit"
                disabled={loading}
              >
                {loading ? "Creating account..." : "Create account"}
              </button>
            </form>

            <p className="register-login">
              Already have an account?{" "}
              <Link to="/login">Sign in</Link>
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
