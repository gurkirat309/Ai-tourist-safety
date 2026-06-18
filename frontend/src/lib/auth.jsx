import { createContext, useContext, useEffect, useState } from "react";
import { api, setToken, getToken } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // { id, email, role, tourist_id }
  const [loading, setLoading] = useState(true);

  // On load, if a token exists, validate it via /auth/me.
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  function _apply(tokenResp) {
    setToken(tokenResp.access_token);
    setUser({
      email: tokenResp.email,
      role: tokenResp.role,
      tourist_id: tokenResp.tourist_id,
    });
    return tokenResp;
  }

  const login = (email, password) =>
    api.login({ email, password }).then(_apply);

  const signup = (payload) => api.signup(payload).then(_apply);

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

// Where a role lands after login.
export function homeForRole(role) {
  return role === "police" ? "/" : "/portal";
}
