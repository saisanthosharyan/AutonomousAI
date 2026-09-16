import { createContext, useContext, useEffect, useState } from "react";
import api from "../api/api";

const AUTH_TOKEN_KEY = "autodev_access_token";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadUser = async () => {
      const storedToken = localStorage.getItem(AUTH_TOKEN_KEY);

      if (!storedToken) {
        setLoading(false);
        return;
      }

      try {
        const response = await api.get("/auth/me");
        setUser(response.data);
      } catch (error) {
        console.error(
          "Failed to restore authentication:",
          error,
        );

        localStorage.removeItem(AUTH_TOKEN_KEY);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    loadUser();
  }, []);

  const login = async (username, password) => {
    const response = await api.post("/auth/login", {
      username,
      password,
    });

    const accessToken = response.data.access_token;

    localStorage.setItem(
      AUTH_TOKEN_KEY,
      accessToken,
    );

    const meResponse = await api.get("/auth/me");

    setUser(meResponse.data);

    return meResponse.data;
  };

  const register = async (
    username,
    email,
    password,
  ) => {
    const response = await api.post("/auth/register", {
      username,
      email,
      password,
    });

    return response.data;
  };

  const logout = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        isAuthenticated: Boolean(user),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider",
    );
  }

  return context;
}
