import { Activity, Bot, Boxes, CircleUserRound, Gauge, Menu, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

const navigation = [
  { to: "/dashboard", label: "Dashboard", icon: Gauge },
  { to: "/hardware", label: "Hardware Graph", icon: Boxes },
  { to: "/doctor", label: "AI Doctor", icon: Bot },
];

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="app-shell">
      <aside className={menuOpen ? "sidebar sidebar--open" : "sidebar"}>
        <div className="brand-row">
          <NavLink className="brand" to="/dashboard" onClick={() => setMenuOpen(false)}>
            <span className="brand__mark" aria-hidden="true"><Activity size={22} strokeWidth={2.5} /></span>
            <span><strong>NeXus</strong><small>Hardware Doctor</small></span>
          </NavLink>
          <button className="icon-button sidebar__close" type="button" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={20} /></button>
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`} key={to} to={to} onClick={() => setMenuOpen(false)}>
              <Icon size={19} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="demo-device">
            <span className="demo-device__icon"><Activity size={18} /></span>
            <span><strong>Demo rig</strong><small>ESP32-S3 · Online</small></span>
            <span className="online-dot" aria-label="Online" />
          </div>
          <p>MVP workspace · Build 0.1</p>
        </div>
      </aside>

      {menuOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}

      <div className="app-content">
        <header className="topbar">
          <button className="icon-button mobile-menu" type="button" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Menu size={21} /></button>
          <div className="topbar__status"><span className="online-dot" aria-hidden="true" />Live telemetry</div>
          <div className="topbar__actions">
            <span className="demo-badge">LIVE DEMO</span>
            <button className="profile-button" type="button" aria-label="Open team profile"><CircleUserRound size={23} /><span>Little Boyz</span></button>
          </div>
        </header>
        <main className="page-shell"><Outlet /></main>
      </div>
    </div>
  );
}
