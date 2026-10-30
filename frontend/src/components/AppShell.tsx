import { Activity, Bot, Boxes, Gauge, Menu, RefreshCw, UsersRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useHardwareMonitor } from "../realtime/HardwareMonitorContext";
import { useI18n, type Language } from "../i18n/I18nContext";

function ageLabel(timestamp: number | null, now: number | null, language: Language) {
  const text = (en: string, vi: string) => language === "vi" ? vi : en;
  if (!timestamp) return text("no data yet", "chưa có dữ liệu");
  if (!now) return text("just updated", "vừa cập nhật");
  const seconds = Math.max(0, Math.floor((now - timestamp) / 1000));
  if (seconds < 2) return text("just updated", "vừa cập nhật");
  if (seconds < 60) return text(`${seconds}s ago`, `${seconds} giây trước`);
  return text(`${Math.floor(seconds / 60)}m ago`, `${Math.floor(seconds / 60)} phút trước`);
}

export function AppShell() {
  const { language, setLanguage, text } = useI18n();
  const [menuOpen, setMenuOpen] = useState(false);
  const [now, setNow] = useState<number | null>(null);
  const {
    snapshot,
    hardwareProfile,
    streamStatus,
    lastUpdatedAt,
    retryAttempt,
    reconnect,
  } = useHardwareMonitor();
  const navigation = [
    { to: "/dashboard", label: text("Overview", "Tổng quan"), icon: Gauge },
    { to: "/hardware", label: text("Hardware Graph", "Sơ đồ phần cứng"), icon: Boxes },
    { to: "/doctor", label: text("AI Doctor", "Bác sĩ AI"), icon: Bot },
  ];
  const isLive = streamStatus === "live" && snapshot?.connection.status === "connected";
  const dataSource = snapshot?.telemetry?.quality.source;
  const sourceLabel = dataSource === "device"
    ? "DEVICE LIVE"
    : dataSource === "replay"
      ? "REPLAY"
      : dataSource === "simulator"
        ? "SIMULATOR"
        : "OFFLINE";
  const sourceIsSynthetic = dataSource === "replay" || dataSource === "simulator";
  const controllerName = hardwareProfile?.controller.model ?? text("board in the profile", "board trong profile");
  const connectionLabel = isLive
    ? `${snapshot?.connection.port ?? hardwareProfile?.transport.type ?? "transport"} · ${sourceLabel}`
    : streamStatus === "live"
      ? text(`Looking for ${controllerName}`, `Đang tìm ${controllerName}`)
      : streamStatus === "reconnecting"
        ? text(`Reconnecting${retryAttempt ? ` · attempt ${retryAttempt}` : ""}`, `Đang nối lại${retryAttempt ? ` · lần ${retryAttempt}` : ""}`)
        : text("Backend is not ready", "Backend chưa sẵn sàng");
  const roleOrder = ["controller", "power_monitor", "motor_driver", "actuator"] as const;
  const hardwareLabel = hardwareProfile
    ? roleOrder.map((role) => hardwareProfile.components.find(
        (item) => item.component_id === hardwareProfile.roles[role],
      )?.model).filter(Boolean).join(" · ")
    : text("Loading hardware profile", "Đang tải hardware profile");

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 10_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">{text("Skip to main content", "Bỏ qua tới nội dung chính")}</a>
      <aside className={menuOpen ? "sidebar sidebar--open" : "sidebar"} aria-label={text("NeXus navigation", "Điều hướng NeXus")}>
        <div className="brand-row">
          <NavLink className="brand" to="/dashboard" onClick={() => setMenuOpen(false)} aria-label={text("NeXus — go to overview", "NeXus — về trang tổng quan")}>
            <span className="brand__mark" aria-hidden="true"><Activity size={22} strokeWidth={2.5} /></span>
            <span><strong>NeXus</strong><small>Hardware Doctor</small></span>
          </NavLink>
          <button className="icon-button sidebar__close" type="button" aria-label={text("Close navigation", "Đóng điều hướng")} onClick={() => setMenuOpen(false)}><X size={20} /></button>
        </div>

        <nav className="primary-nav" aria-label={text("Primary navigation", "Điều hướng chính")}>
          <span className="nav-label">{text("Workspace", "Không gian làm việc")}</span>
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`} key={to} to={to} onClick={() => setMenuOpen(false)}>
              <Icon size={19} aria-hidden="true" /><span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="language-switcher" role="group" aria-label={text("Language", "Ngôn ngữ")}>
            <button type="button" className={language === "en" ? "is-active" : ""} aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button>
            <button type="button" className={language === "vi" ? "is-active" : ""} aria-pressed={language === "vi"} onClick={() => setLanguage("vi")}>VI</button>
          </div>
          <div className="demo-device" aria-live="polite">
            <span className="demo-device__icon"><Activity size={18} /></span>
            <span><strong>{text("MVP demo rig", "Bộ demo MVP")}</strong><small>{connectionLabel}</small></span>
            <span className={`online-dot${isLive ? "" : " online-dot--offline"}`} aria-label={isLive ? text("Receiving data", "Đang nhận dữ liệu") : text("No data", "Chưa nhận dữ liệu")} />
          </div>
          <p>{hardwareLabel}</p>
        </div>
      </aside>

      {menuOpen && <button className="sidebar-scrim" aria-label={text("Close navigation", "Đóng điều hướng")} onClick={() => setMenuOpen(false)} />}

      <div className="app-content">
        <header className="topbar">
          <button className="icon-button mobile-menu" type="button" aria-label={text("Open navigation", "Mở điều hướng")} onClick={() => setMenuOpen(true)}><Menu size={21} /></button>
          <div className="topbar__status" role="status" aria-live="polite">
            <span className={`online-dot${isLive ? "" : " online-dot--offline"}`} aria-hidden="true" />
            <span><strong>{connectionLabel}</strong><small>{ageLabel(lastUpdatedAt, now, language)}</small></span>
          </div>
          <div className="topbar__actions">
            {!isLive && <button className="topbar__reconnect" type="button" onClick={reconnect}><RefreshCw size={15} /> {text("Reconnect", "Nối lại")}</button>}
            <span className={`demo-badge${sourceIsSynthetic ? " demo-badge--replay" : ""}`}>{sourceLabel}</span>
            <span className="team-chip" aria-label={text("Little Boyz team", "Nhóm Little Boyz")}><UsersRound size={19} /><span>Little Boyz</span></span>
          </div>
        </header>
        <main className="page-shell" id="main-content" tabIndex={-1}><Outlet /></main>
      </div>
    </div>
  );
}
