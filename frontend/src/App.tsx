import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { RouteMeta } from "./components/RouteMeta";
import { HardwareMonitorProvider } from "./realtime/HardwareMonitorContext";

const AIDoctorPage = lazy(() =>
  import("./pages/AIDoctorPage").then((module) => ({ default: module.AIDoctorPage })),
);
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })),
);
const HardwareGraphPage = lazy(() =>
  import("./pages/HardwareGraphPage").then((module) => ({ default: module.HardwareGraphPage })),
);

function PageLoader() {
  return <div className="page-loader" role="status">Đang mở màn hình…</div>;
}

export function App() {
  return (
    <HardwareMonitorProvider>
      <RouteMeta />
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="hardware" element={<HardwareGraphPage />} />
            <Route path="doctor" element={<AIDoctorPage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </HardwareMonitorProvider>
  );
}
