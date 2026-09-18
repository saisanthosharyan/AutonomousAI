import { Bell, Search, Sparkles } from "lucide-react";

export default function Navbar() {
  return (
    <header className="aio-navbar">
      <div className="aio-navbar-left">
        <div className="aio-navbar-title">
          <Sparkles size={17} />
          <span>AI Workspace</span>
        </div>
      </div>

      <div className="aio-navbar-center">
        <div className="aio-search">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search projects..."
            aria-label="Search projects"
          />
          <span className="aio-search-shortcut">⌘ K</span>
        </div>
      </div>

      <div className="aio-navbar-right">
        <div className="aio-status">
          <span className="aio-status-dot" />
          <span>AI Online</span>
        </div>

        <button
          type="button"
          className="aio-icon-button"
          aria-label="Notifications"
        >
          <Bell size={17} />
        </button>

        <div className="aio-navbar-avatar">S</div>
      </div>
    </header>
  );
}
