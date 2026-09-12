import { Activity, Bot, Boxes, Gauge, Menu, RefreshCw, UsersRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";

const navigation = [
  { to: "/dashboard", label: "Tổng quan", icon: Gauge },
  { to: "/hardware", label: "Sơ đồ phần cứng", icon: Boxes },
  { to: "/doctor", label: "Bác sĩ AI", icon: Bot },
];

function ageLabel(timestamp: number | null, now: number | null) {
  if (!timestamp) return "chưa có dữ liệu";
  if (!now) return "vừa cập nhật";
  const seconds = Math.max(0, Math.floor((now - timestamp) / 1000));
  if (seconds < 2) return "vừa cập nhật";
  if (seconds < 60) return `${seconds} giây trước`;
  return `${Math.floor(seconds / 60)} phút trước`;
}

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [now, setNow] = useState<number | null>(null);
  const { snapshot, streamStatus, lastUpdatedAt, retryAttempt, reconnect } = useHardwareMonitor();
  const isLive = streamStatus === "live" && snapshot.connection.status === "connected";
  const isReplay = snapshot.telemetry?.quality.source === "replay";
  const connectionLabel = isLive
    ? `${snapshot.connection.port ?? "USB"} · ${isReplay ? "Replay" : "Realtime"}`
    : streamStatus === "live"
      ? "Đang tìm ESP32"
      : streamStatus === "reconnecting"
        ? `Đang nối lại${retryAttempt ? ` · lần ${retryAttempt}` : ""}`
        : "Backend chưa sẵn sàng";

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 10_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Bỏ qua tới nội dung chính</a>
      <aside className={menuOpen ? "sidebar sidebar--open" : "sidebar"} aria-label="Điều hướng NeXus">
        <div className="brand-row">
          <NavLink className="brand" to="/dashboard" onClick={() => setMenuOpen(false)} aria-label="NeXus — về trang tổng quan">
            <span className="brand__mark" aria-hidden="true"><Activity size={22} strokeWidth={2.5} /></span>
            <span><strong>NeXus</strong><small>Hardware Doctor</small></span>
          </NavLink>
          <button className="icon-button sidebar__close" type="button" aria-label="Đóng điều hướng" onClick={() => setMenuOpen(false)}><X size={20} /></button>
        </div>

        <nav className="primary-nav" aria-label="Điều hướng chính">
          <span className="nav-label">Không gian làm việc</span>
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`} key={to} to={to} onClick={() => setMenuOpen(false)}>
              <Icon size={19} aria-hidden="true" /><span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="demo-device" aria-live="polite">
            <span className="demo-device__icon"><Activity size={18} /></span>
            <span><strong>Bộ demo MVP</strong><small>{connectionLabel}</small></span>
            <span className={`online-dot${isLive ? "" : " online-dot--offline"}`} aria-label={isLive ? "Đang nhận dữ liệu" : "Chưa nhận dữ liệu"} />
          </div>
          <p>GOOUUU S3 · INA226 · L298N · JGB37-520</p>
        </div>
      </aside>

      {menuOpen && <button className="sidebar-scrim" aria-label="Đóng điều hướng" onClick={() => setMenuOpen(false)} />}

      <div className="app-content">
        <header className="topbar">
          <button className="icon-button mobile-menu" type="button" aria-label="Mở điều hướng" onClick={() => setMenuOpen(true)}><Menu size={21} /></button>
          <div className="topbar__status" role="status" aria-live="polite">
            <span className={`online-dot${isLive ? "" : " online-dot--offline"}`} aria-hidden="true" />
            <span><strong>{connectionLabel}</strong><small>{ageLabel(lastUpdatedAt, now)}</small></span>
          </div>
          <div className="topbar__actions">
            {!isLive && <button className="topbar__reconnect" type="button" onClick={reconnect}><RefreshCw size={15} /> Nối lại</button>}
            <span className={`demo-badge${isReplay ? " demo-badge--replay" : ""}`}>{isReplay ? "REPLAY" : "LIVE MVP"}</span>
            <span className="team-chip" aria-label="Nhóm Little Boyz"><UsersRound size={19} /><span>Little Boyz</span></span>
          </div>
        </header>
        <main className="page-shell" id="main-content" tabIndex={-1}><Outlet /></main>
      </div>
    </div>
  );
}
