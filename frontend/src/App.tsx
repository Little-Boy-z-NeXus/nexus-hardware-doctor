import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AIDoctorPage } from "./pages/AIDoctorPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HardwareGraphPage } from "./pages/HardwareGraphPage";
import { HardwareMonitorProvider } from "./realtime/HardwareMonitorContext";

export function App() {
  return (
    <HardwareMonitorProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="hardware" element={<HardwareGraphPage />} />
          <Route path="doctor" element={<AIDoctorPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </HardwareMonitorProvider>
  );
}
