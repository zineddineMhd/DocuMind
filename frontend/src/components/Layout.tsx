import { ChevronDown, Clock, FileText, FolderClosed, Home, Layers, LogOut, Menu, MessageSquare, Settings, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useApp } from "../hooks/useApp";
import { formatBytes } from "../services/api";
import { Toasts } from "./ui";

const NAV = [
  { to: "/", label: "Accueil", icon: Home, end: true },
  { to: "/chat", label: "Discuter", icon: MessageSquare },
  { to: "/documents", label: "Mes documents", icon: FileText },
  { to: "/historique", label: "Historique", icon: Clock },
  { to: "/collections", label: "Collections", icon: FolderClosed },
  { to: "/parametres", label: "Paramètres", icon: Settings },
];

export function Logo({ light = true }: { light?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-white shadow-lg shadow-brand-900/30">
        <Layers size={19} />
      </span>
      <span className={`text-xl font-bold tracking-tight ${light ? "text-white" : "text-ink-900"}`}>DocuMind</span>
    </div>
  );
}

export default function Layout() {
  const { user, workspaces, workspace, selectWorkspace, stats, signOut } = useApp();
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const navigate = useNavigate();
  const used = stats?.storage_used ?? 0;
  const quota = stats?.storage_quota ?? 1;
  const initials = (user?.name || user?.email || "?").split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((s) => s[0]!.toUpperCase()).join("");

  return (
    <div className="flex h-full">
      {open && <div className="fixed inset-0 z-30 bg-ink-900/50 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col bg-gradient-to-b from-[#17143a] via-[#1d1848] to-[#2a1f66] p-4 text-white transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="mb-6 flex items-center justify-between px-1 pt-1">
          <Logo />
          <button className="rounded-lg p-1.5 text-white/70 hover:bg-white/10 lg:hidden" onClick={() => setOpen(false)} aria-label="Fermer le menu"><X size={18} /></button>
        </div>

        <label className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wider text-white/50" htmlFor="ws-select">Espace de travail</label>
        <div className="relative mb-5">
          <select id="ws-select" value={workspace?.id ?? ""} onChange={(e) => selectWorkspace(e.target.value)}
            className="w-full appearance-none rounded-xl border border-white/10 bg-white/10 py-2.5 pl-3 pr-9 text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-brand-400">
            {workspaces.map((w) => <option key={w.id} value={w.id} className="text-ink-900">{w.name}</option>)}
          </select>
          <ChevronDown size={16} className="pointer-events-none absolute right-3 top-3 text-white/60" />
        </div>

        <nav className="flex flex-col gap-1" aria-label="Navigation principale">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-[15px] font-medium transition ${
                isActive ? "bg-brand-600 text-white shadow-lg shadow-brand-900/40" : "text-white/75 hover:bg-white/10 hover:text-white"}`}>
              <Icon size={19} />{label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto space-y-3">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3.5">
            <p className="text-sm font-semibold">Espace de stockage</p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/15" role="progressbar"
              aria-valuenow={Math.round((used / quota) * 100)} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full rounded-full bg-gradient-to-r from-brand-300 to-brand-400" style={{ width: `${Math.min(100, Math.max(2, (used / quota) * 100))}%` }} />
            </div>
            <p className="mt-2 text-xs text-white/60">{formatBytes(used)} / {formatBytes(quota)}</p>
          </div>
          <div className="relative">
            {menu && (
              <div className="absolute bottom-full left-0 mb-2 w-full overflow-hidden rounded-xl border border-white/10 bg-[#241d57] py-1 shadow-xl">
                <button className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-sm hover:bg-white/10"
                  onClick={() => { setMenu(false); navigate("/parametres"); }}><Settings size={15} />Paramètres</button>
                <button className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-sm text-red-200 hover:bg-white/10"
                  onClick={signOut}><LogOut size={15} />Se déconnecter</button>
              </div>
            )}
            <button onClick={() => setMenu((m) => !m)} aria-expanded={menu}
              className="flex w-full items-center gap-3 rounded-2xl border border-white/10 bg-white/5 p-3 text-left hover:bg-white/10">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-500 text-sm font-bold">{initials}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">{user?.name}</span>
                <span className="block truncate text-xs text-white/55">{user?.email}</span>
              </span>
              <ChevronDown size={16} className="text-white/60" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-[#e9e7f3] bg-white px-4 py-2.5 lg:hidden">
          <button className="icon-btn" onClick={() => setOpen(true)} aria-label="Ouvrir le menu"><Menu size={20} /></button>
          <Logo light={false} />
        </header>
        <main className="scroll-thin min-h-0 flex-1 overflow-auto"><Outlet /></main>
      </div>
      <Toasts />
    </div>
  );
}
