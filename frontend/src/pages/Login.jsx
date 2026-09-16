import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Sparkles } from "lucide-react";
import toast from "react-hot-toast";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-500/10 border border-cyan-400/20">
            <Sparkles className="text-cyan-400" size={32} />
          </div>

          <h1 className="text-3xl font-bold">
            Welcome to AutoDev{" "}
            <span className="text-cyan-400">AI</span>
          </h1>

          <p className="mt-3 text-gray-400">
            Sign in to continue building with your AI software engineer.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-gray-800 bg-gray-900/80 p-7 shadow-2xl"
        >
          <div className="space-y-5">
            <div>
              <label
                htmlFor="username"
                className="mb-2 block text-sm font-medium text-gray-300"
              >
                Username
              </label>

              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Enter your username"
                className="w-full rounded-xl border border-gray-700 bg-gray-950 px-4 py-3 text-white outline-none transition placeholder:text-gray-600 focus:border-cyan-400"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-2 block text-sm font-medium text-gray-300"
              >
                Password
              </label>

              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                  className="w-full rounded-xl border border-gray-700 bg-gray-950 px-4 py-3 pr-12 text-white outline-none transition placeholder:text-gray-600 focus:border-cyan-400"
                />

                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-2 text-gray-400 transition hover:bg-gray-800 hover:text-white"
                  aria-label={
                    showPassword
                      ? "Hide password"
                      : "Show password"
                  }
                >
                  {showPassword ? (
                    <EyeOff size={19} />
                  ) : (
                    <Eye size={19} />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-cyan-500 px-4 py-3 font-semibold text-black transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </div>

          <p className="mt-6 text-center text-sm text-gray-400">
            Don't have an account?{" "}
            <Link
              to="/register"
              className="font-medium text-cyan-400 hover:text-cyan-300"
            >
              Create one
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
