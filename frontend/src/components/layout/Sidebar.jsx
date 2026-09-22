import { NavLink, useNavigate } from "react-router-dom";
import {
  Home,
  FolderGit2,
  Settings,
  Plus,
  Sparkles,
  MessageSquare,
} from "lucide-react";

export default function Sidebar() {
  const navigate = useNavigate();

  const menu = [
    {
      name: "Home",
      icon: Home,
      path: "/",
    },
    {
      name: "Projects",
      icon: FolderGit2,
      path: "/projects",
    },
  ];

  const tools = [
    {
      name: "Settings",
      icon: Settings,
      path: "#",
    },
  ];

  const handleNewChat = () => {
    navigate("/");
    window.dispatchEvent(
      new CustomEvent("autodev:new-chat"),
    );
  };

  return (
    <aside className="aio-sidebar">
      <div className="aio-sidebar-brand">
        <div className="aio-brand-mark">
          <Sparkles size={18} strokeWidth={2.2} />
        </div>

        <div className="aio-brand-text">
          <span>AutoDev</span>
          <span>AI</span>
        </div>
      </div>

      <button
        type="button"
        className="aio-new-build"
        onClick={handleNewChat}
      >
        <Plus size={18} strokeWidth={2.4} />
        <span>New Chat</span>
      </button>

      <nav className="aio-sidebar-nav">
        <div className="aio-nav-section">
          <span className="aio-nav-label">
            WORKSPACE
          </span>

          {menu.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.name}
                to={item.path}
                className={({ isActive }) =>
                  `aio-nav-item ${
                    isActive ? "active" : ""
                  }`
                }
              >
                <Icon
                  size={18}
                  strokeWidth={2}
                />

                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </div>

        <div className="aio-sidebar-history">
          <div className="aio-sidebar-history-heading">
            <span className="aio-nav-label">
              RECENT CHATS
            </span>

            <MessageSquare size={13} />
          </div>

          <div
            id="autodev-chat-history"
            className="aio-sidebar-history-list"
          >
            <div className="aio-sidebar-history-empty">
              <span>No chats yet</span>
            </div>
          </div>
        </div>

        <div className="aio-nav-divider" />

        <div className="aio-nav-section">
          <span className="aio-nav-label">
            TOOLS
          </span>

          {tools.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.name}
                to={item.path}
                className="aio-nav-item"
              >
                <Icon
                  size={18}
                  strokeWidth={2}
                />

                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </div>
      </nav>

      <div className="aio-sidebar-bottom">
        <div className="aio-user-card">
          <div className="aio-user-avatar">
            S
          </div>

          <div className="aio-user-info">
            <span className="aio-user-name">
              Santhosh
            </span>

            <span className="aio-user-plan">
              Free Plan
            </span>
          </div>

          <div className="aio-online-dot" />
        </div>

        <div className="aio-version">
          AutoDev AI <span>v1.0</span>
        </div>
      </div>
    </aside>
  );
}