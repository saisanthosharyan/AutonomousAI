import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Sparkles } from "lucide-react";
import toast from "react-hot-toast";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-500/10 border border-cyan-400/20">
            <Sparkles className="text-cyan-400" size={32} />
          </div>

          <h1 className="text-3xl font-bold">
            Create your AutoDev <span className="text-cyan-400">AI</span> account
          </h1>

          <p className="mt-3 text-gray-400">
            Start building software with your autonomous AI engineer.
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
                placeholder="Choose a username"
                className="w-full rounded-xl border border-gray-700 bg-gray-950 px-4 py-3 text-white outline-none transition placeholder:text-gray-600 focus:border-cyan-400"
              />
            </div>

            <div>
              <label
                htmlFor="register-email"
                className="mb-2 block text-sm font-medium text-gray-300"
              >
                Email
              </label>

              <input
                id="register-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-xl border border-gray-700 bg-gray-950 px-4 py-3 text-white outline-none transition placeholder:text-gray-600 focus:border-cyan-400"
              />
            </div>

            <div>
              <label
                htmlFor="register-password"
                className="mb-2 block text-sm font-medium text-gray-300"
              >
                Password
              </label>

              <div className="relative">
                <input
                  id="register-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 8 characters"
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

            <div>
              <label
                htmlFor="confirm-password"
                className="mb-2 block text-sm font-medium text-gray-300"
              >
                Confirm Password
              </label>

              <div className="relative">
                <input
                  id="confirm-password"
                  type={showConfirmPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(event.target.value)
                  }
                  placeholder="Re-enter your password"
                  className="w-full rounded-xl border border-gray-700 bg-gray-950 px-4 py-3 pr-12 text-white outline-none transition placeholder:text-gray-600 focus:border-cyan-400"
                />

                <button
                  type="button"
                  onClick={() =>
                    setShowConfirmPassword((value) => !value)
                  }
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-2 text-gray-400 transition hover:bg-gray-800 hover:text-white"
                  aria-label={
                    showConfirmPassword
                      ? "Hide password"
                      : "Show password"
                  }
                >
                  {showConfirmPassword ? (
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
              {loading ? "Creating account..." : "Create Account"}
            </button>
          </div>

          <p className="mt-6 text-center text-sm text-gray-400">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium text-cyan-400 hover:text-cyan-300"
            >
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
