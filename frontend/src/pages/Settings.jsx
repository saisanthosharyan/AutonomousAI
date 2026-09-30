import { useNavigate } from "react-router-dom";
import {
  LogOut,
  Mail,
  Settings as SettingsIcon,
  ShieldCheck,
  User,
} from "lucide-react";

import { useAuth } from "../context/useAuth";

export default function Settings() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const username = user?.username || "User";
  const email = user?.email || "Not available";
  const accountId = user?.id ?? "—";

  const initial =
    username.charAt(0).toUpperCase() || "U";

  const handleLogout = () => {
    logout();
    navigate("/login", {
      replace: true,
    });
  };

  return (
    <main className="aio-settings-page">
      <div className="aio-settings-header">
        <div>
          <div className="aio-settings-kicker">
            <SettingsIcon size={15} />
            <span>SETTINGS</span>
          </div>

          <h1>Account settings</h1>

          <p>
            View your AutoDev AI account and
            application information.
          </p>
        </div>
      </div>

      <div className="aio-settings-grid">
        <section className="aio-settings-card">
          <div className="aio-settings-card-heading">
            <div className="aio-settings-avatar">
              {initial}
            </div>

            <div>
              <h2>{username}</h2>
              <span>AutoDev AI account</span>
            </div>
          </div>

          <div className="aio-settings-details">
            <div className="aio-settings-detail">
              <User size={16} />

              <div>
                <span>Username</span>
                <strong>{username}</strong>
              </div>
            </div>

            <div className="aio-settings-detail">
              <Mail size={16} />

              <div>
                <span>Email</span>
                <strong>{email}</strong>
              </div>
            </div>

            <div className="aio-settings-detail">
              <ShieldCheck size={16} />

              <div>
                <span>Account ID</span>
                <strong>{accountId}</strong>
              </div>
            </div>
          </div>
        </section>

        <section className="aio-settings-card">
          <div className="aio-settings-section-title">
            <h2>Application</h2>

            <p>
              Information about this AutoDev AI
              installation.
            </p>
          </div>

          <div className="aio-settings-app-info">
            <div>
              <span>Application</span>
              <strong>AutoDev AI</strong>
            </div>

            <div>
              <span>Version</span>
              <strong>v1.0</strong>
            </div>

            <div>
              <span>Workspace</span>
              <strong>Autonomous Development</strong>
            </div>
          </div>
        </section>

        <section className="aio-settings-card aio-settings-danger">
          <div className="aio-settings-section-title">
            <h2>Session</h2>

            <p>
              Sign out of your current AutoDev AI
              session.
            </p>
          </div>

          <button
            type="button"
            className="aio-settings-logout"
            onClick={handleLogout}
          >
            <LogOut size={16} />
            <span>Sign out</span>
          </button>
        </section>
      </div>
    </main>
  );
}