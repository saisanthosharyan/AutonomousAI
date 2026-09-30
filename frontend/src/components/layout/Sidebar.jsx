import {
  useEffect,
  useState,
} from "react";

import {
  NavLink,
  useNavigate,
} from "react-router-dom";
import { useAuth } from "../../context/useAuth";

import {
  FolderGit2,
  Home,
  MessageSquare,
  Plus,
  Settings,
  Sparkles,
} from "lucide-react";

const CHAT_HISTORY_KEY = "autodev_chat_history";

function loadChatHistory() {
  try {
    const saved = localStorage.getItem(
      CHAT_HISTORY_KEY,
    );

    if (!saved) {
      return [];
    }

    const parsed = JSON.parse(saved);

    return Array.isArray(parsed)
      ? parsed
      : [];
  } catch (error) {
    console.error(
      "Failed to load sidebar chat history:",
      error,
    );

    return [];
  }
}

export default function Sidebar() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const username = user?.username || "User";
  const email = user?.email || "Signed in";

  const userInitial =
    username.charAt(0).toUpperCase() || "U";

  const [chatHistory, setChatHistory] =
    useState(loadChatHistory);

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
      path: "/settings",
    },
  ];

  useEffect(() => {
    const handleHistoryUpdated = (event) => {
      if (Array.isArray(event.detail)) {
        setChatHistory(event.detail);
        return;
      }

      setChatHistory(loadChatHistory());
    };

    const handleStorage = (event) => {
      if (
        event.key === CHAT_HISTORY_KEY
      ) {
        setChatHistory(loadChatHistory());
      }
    };

    window.addEventListener(
      "autodev-history-updated",
      handleHistoryUpdated,
    );

    window.addEventListener(
      "storage",
      handleStorage,
    );

    return () => {
      window.removeEventListener(
        "autodev-history-updated",
        handleHistoryUpdated,
      );

      window.removeEventListener(
        "storage",
        handleStorage,
      );
    };
  }, []);

  const handleNewChat = () => {
    navigate("/");

    window.dispatchEvent(
      new CustomEvent("autodev:new-chat"),
    );
  };

  const handleOpenChat = (chat) => {
    navigate("/");

    window.setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent(
          "autodev:open-chat",
          {
            detail: chat,
          },
        ),
      );
    }, 0);
  };

  return (
    <aside className="aio-sidebar">
      <div className="aio-sidebar-brand">
        <div className="aio-brand-mark">
          <Sparkles
            size={18}
            strokeWidth={2.2}
          />
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
        <Plus
          size={18}
          strokeWidth={2.4}
        />

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
                    isActive
                      ? "active"
                      : ""
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
            {chatHistory.length === 0 ? (
              <div className="aio-sidebar-history-empty">
                <span>No chats yet</span>
              </div>
            ) : (
              chatHistory
                .slice(0, 8)
                .map((chat) => (
                  <button
                    key={
                      chat.id ||
                      chat.runId ||
                      chat.title
                    }
                    type="button"
                    className="aio-sidebar-history-item"
                    title={chat.title}
                    onClick={() =>
                      handleOpenChat(chat)
                    }
                  >
                    <MessageSquare
                      size={13}
                    />

                    <span>
                      {chat.title}
                    </span>
                  </button>
                ))
            )}
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
            {userInitial}
          </div>

          <div className="aio-user-info">
            <span
              className="aio-user-name"
              title={username}
            >
              {username}
            </span>

            <span
              className="aio-user-plan"
              title={email}
            >
              {email}
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