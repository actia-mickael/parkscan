import { useEffect } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import Layout from "@/components/Layout";
import DashboardPage from "@/pages/DashboardPage";
import LoginPage from "@/pages/LoginPage";
import MismatchesPage from "@/pages/MismatchesPage";
import PassageDetailPage from "@/pages/PassageDetailPage";
import PassagesPage from "@/pages/PassagesPage";
import ResidentDetailPage from "@/pages/ResidentDetailPage";
import ResidentsPage from "@/pages/ResidentsPage";
import SiteDetailPage from "@/pages/SiteDetailPage";
import SitesPage from "@/pages/SitesPage";
import UsersPage from "@/pages/UsersPage";
import VehiclesPage from "@/pages/VehiclesPage";
import { useAuthStore } from "@/stores/authStore";

function RequireAuth() {
  const status = useAuthStore((s) => s.status);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();
  if (status !== "ready") {
    return <p className="p-6 text-sm text-slate-400">Chargement de la session…</p>;
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

function RequireAdmin() {
  const user = useAuthStore((s) => s.user);
  if (user?.role !== "operator_admin") return <Navigate to="/" replace />;
  return <Outlet />;
}

export default function App() {
  const bootstrap = useAuthStore((s) => s.bootstrap);
  const status = useAuthStore((s) => s.status);

  useEffect(() => {
    if (status === "idle") void bootstrap();
  }, [status, bootstrap]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="passages" element={<PassagesPage />} />
          <Route path="passages/:id" element={<PassageDetailPage />} />
          <Route path="mismatches" element={<MismatchesPage />} />
          <Route path="residents" element={<ResidentsPage />} />
          <Route path="residents/:id" element={<ResidentDetailPage />} />
          <Route path="vehicles" element={<VehiclesPage />} />
          <Route path="sites" element={<SitesPage />} />
          <Route path="sites/:id" element={<SiteDetailPage />} />
          <Route element={<RequireAdmin />}>
            <Route path="users" element={<UsersPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
