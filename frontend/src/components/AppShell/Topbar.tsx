import { Menu, ShieldCheck } from "lucide-react";
import type { AppShellController } from "./useAppShell";

export default function Topbar({ app }: { app: AppShellController }) {
  return (
    <header className="topbar">
      <button className="menu-button" type="button"
        onClick={() => app.setSidebarOpen(true)} aria-label="פתיחת תפריט">
        <Menu size={21} />
      </button>
      <div>
        <span>{app.conversation ? "מזהה נוכחי" : "סיכום חדש"}</span>
        <strong dir="ltr">{app.conversation?.root_id || "מזהה חדש"}</strong>
      </div>
      <span className="trust-indicator">
        <ShieldCheck size={16} /> מבוסס ראיות
      </span>
    </header>
  );
}
