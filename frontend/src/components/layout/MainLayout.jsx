import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import "../../styles/Layout.css";

export default function MainLayout({ children }) {
  return (
    <div className="aio-app-shell">
      <Sidebar />

      <div className="aio-content-shell">
        <Navbar />

        <main className="aio-page-content">
          {children}
        </main>
      </div>
    </div>
  );
}