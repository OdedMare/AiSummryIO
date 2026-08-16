import { Menu, ShieldCheck, Trash2 } from "lucide-react";
import { identifierLabel } from "./commands";
import type { AppShellController } from "./useAppShell";
import { isActive } from "./useAppShell";

export default function Topbar({ app }: { app: AppShellController }) {
  return (
    <header className="topbar">
      <button className="menu-button" type="button"
        onClick={() => app.setSidebarOpen(true)} aria-label="פתיחת תפריט">
        <Menu size={21} />
      </button>
      <div>
        <span>{app.conversation ? "מזהה נוכחי" : "סיכום חדש"}</span>
        <strong dir="ltr" title={app.conversation?.root_id || ""}>
          {identifierLabel(app.conversation?.root_id ?? "") || "מזהה חדש"}
        </strong>
      </div>
      <div className="topbar-actions">
        <span className="trust-indicator">
          <ShieldCheck size={16} /> מבוסס ראיות
        </span>
        {app.conversation &&
          <button className="end-conversation" type="button"
            aria-label="סיום ומחיקת השיחה"
            disabled={app.submitting || isActive(app.run)}
            onClick={() => void app.endConversation()}>
            <Trash2 size={15} /><span>סיום ומחיקה</span>
          </button>}
      </div>
    </header>
  );
}
