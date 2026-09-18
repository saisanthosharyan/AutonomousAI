import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  LockKeyhole,
  Moon,
  Sparkles,
  Sun,
  UserRound,
} from "lucide-react";
import toast from "react-hot-toast";
import { useAuth } from "../context/useAuth";
import "../styles/Login.css";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();

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
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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

    if (!username.trim() || !password) {
      toast.error("Please enter your username and password.");
      return;
    }

    try {
      setLoading(true);

      await login(username.trim(), password);

      toast.success("Welcome back to AutoDev AI.");
      navigate("/", { replace: true });
    } catch (error) {
      const detail = error?.response?.data?.detail;

      let message = "Unable to sign in.";

      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message =
          detail
            .map((item) => item?.msg)
            .filter(Boolean)
            .join(", ") || message;
      }

      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const isDark = theme === "dark";

  return (
    <main className="login-page">
      <section className="login-shell">
        <div className="login-brand-panel">
          <div className="login-brand">
            <div className="login-brand-mark">A</div>
            <span className="login-brand-name">AutoDev AI</span>
          </div>

          <div className="login-brand-content">
            <p className="login-eyebrow">
              Autonomous software engineering
            </p>

            <h1>
              Turn ideas
              <br />
              into software.
            </h1>

            <p>
              Describe what you want to build and let AutoDev AI plan, code,
              execute, debug, test, and validate it for you.
            </p>

            <div className="login-feature-list">
              <div className="login-feature">
                <span className="login-feature-icon">
                  <Sparkles size={15} />
                </span>
                AI-powered development workflow
              </div>

              <div className="login-feature">
                <span className="login-feature-icon">
                  <Check size={15} />
                </span>
                Automated testing and validation
              </div>

              <div className="login-feature">
                <span className="login-feature-icon">
                  <ArrowRight size={15} />
                </span>
                From prompt to working project
              </div>
            </div>
          </div>

          <span className="login-brand-footer">
            Build faster. Iterate smarter.
          </span>
        </div>

        <div className="login-form-panel">
          <button
            type="button"
            className="login-theme-toggle"
            onClick={toggleTheme}
            aria-label={
              isDark ? "Switch to light theme" : "Switch to dark theme"
            }
            title={isDark ? "Light theme" : "Dark theme"}
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          <div className="login-form-container">
            <div className="login-form-header">
              <h2>Welcome back</h2>
              <p>Sign in to continue building with AutoDev AI.</p>
            </div>

            <form className="login-form" onSubmit={handleSubmit}>
              <div className="login-field">
                <label htmlFor="username">Username</label>

                <div className="login-input-wrapper">
                  <UserRound className="login-input-icon" />

                  <input
                    id="username"
                    name="username"
                    type="text"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder="Enter your username"
                    className="login-input"
                    autoComplete="username"
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="login-field">
                <label htmlFor="password">Password</label>

                <div className="login-input-wrapper">
                  <LockKeyhole className="login-input-icon" />

                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Enter your password"
                    className="login-input"
                    autoComplete="current-password"
                    disabled={loading}
                  />

                  <button
                    type="button"
                    className="login-password-toggle"
                    onClick={() => setShowPassword((current) => !current)}
                    aria-label={
                      showPassword ? "Hide password" : "Show password"
                    }
                    title={showPassword ? "Hide password" : "Show password"}
                    disabled={loading}
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                className="login-submit"
                disabled={loading}
              >
                {loading ? "Signing in..." : "Sign in"}
              </button>
            </form>

            <p className="login-register">
              Don't have an account?{" "}
              <Link to="/register">Create an account</Link>
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}