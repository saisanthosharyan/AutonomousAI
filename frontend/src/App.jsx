import { Routes, Route, Outlet } from "react-router-dom";

import MainLayout from "./components/layout/MainLayout";
import ProtectedRoute from "./components/auth/ProtectedRoute";

import Home from "./pages/Home";
import Projects from "./pages/Projects";
import ProjectDetails from "./pages/ProjectDetails";
import Login from "./pages/Login";
import Register from "./pages/Register";
import History from "./pages/History";

function ProtectedLayout() {
  return (
    <MainLayout>
      <Outlet />
    </MainLayout>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/projects" element={<Projects />} />
          <Route
            path="/projects/:projectId"
            element={<ProjectDetails />}
          />
          <Route path="/history" element={<History />} />
        </Route>
      </Route>
    </Routes>
  );
}

export default App;
