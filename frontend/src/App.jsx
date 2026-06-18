import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import { RequireAuth, RequireRole } from "./components/guards";
import Dashboard from "./pages/Dashboard";
import TouristPortal from "./pages/TouristPortal";
import Login from "./pages/Login";
import Signup from "./pages/Signup";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      <Route element={<RequireAuth />}>
        <Route path="/" element={<Layout />}>
          <Route
            index
            element={
              <RequireRole role="police">
                <Dashboard />
              </RequireRole>
            }
          />
          <Route
            path="portal"
            element={
              <RequireRole role="tourist">
                <TouristPortal />
              </RequireRole>
            }
          />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
