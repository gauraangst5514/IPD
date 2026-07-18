import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "./store/auth";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ClaimsPage from "./pages/ClaimsPage";
import NewClaimPage from "./pages/NewClaimPage";
import ClaimDetailPage from "./pages/ClaimDetailPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((state) => state.token);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="claims" element={<ClaimsPage />} />
        <Route path="claims/new" element={<NewClaimPage />} />
        <Route path="claims/:id" element={<ClaimDetailPage />} />
        <Route path="review" element={<ReviewQueuePage />} />
      </Route>
    </Routes>
  );
}
