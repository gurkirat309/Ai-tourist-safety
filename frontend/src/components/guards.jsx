import { Navigate, Outlet } from "react-router-dom";
import { useAuth, homeForRole } from "../lib/auth";
import { Spinner } from "./ui";

// Blocks until auth state resolves; redirects to /login if unauthenticated.
export function RequireAuth() {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

// Restricts a route to a role; otherwise sends the user to their own home.
export function RequireRole({ role, children }) {
  const { user } = useAuth();
  if (user && user.role !== role) {
    return <Navigate to={homeForRole(user.role)} replace />;
  }
  return children;
}
