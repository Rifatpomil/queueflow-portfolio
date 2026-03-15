import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { Login } from "./pages/Login";
import { OperatorQueue } from "./pages/OperatorQueue";
import { SignageDisplay } from "./pages/SignageDisplay";
import { AdminPanel } from "./pages/AdminPanel";
import { Kiosk } from "./pages/Kiosk";
import { useAuth } from "./hooks/useAuth";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        {/* Public – no auth */}
        <Route path="/signage/:locationId" element={<SignageDisplay />} />
        <Route path="/kiosk/:locationId" element={<Kiosk />} />
        <Route path="/kiosk" element={<Navigate to="/kiosk/00000000-0000-0000-0000-000000000020" replace />} />
        {/* Protected routes */}
        <Route
          path="/"
          element={
            <RequireAuth>
              <>
                <Navbar />
                <main style={{ padding: "24px", maxWidth: "1200px", margin: "0 auto" }}>
                  <OperatorQueue />
                </main>
              </>
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAuth>
              <>
                <Navbar />
                <main style={{ padding: "24px", maxWidth: "1200px", margin: "0 auto" }}>
                  <AdminPanel />
                </main>
              </>
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
