import {
  Beaker, Bot, History, Moon, PanelRightClose, Plus, Settings, Sun, Workflow,
} from "lucide-react";
import BrandMark from "./BrandMark";
import { identifierLabel } from "./commands";
import type { AppShellController } from "./useAppShell";

export default function Sidebar({ app }: { app: AppShellController }) {
  return (
    <aside className={`sidebar ${app.sidebarOpen ? "open" : ""}`}>
      <Brand onClose={() => app.setSidebarOpen(false)} />
      <button className="new-summary" type="button"
        onClick={app.conversation
          ? () => void app.endConversation()
          : app.startNew}>
        <Plus size={18} /> סיכום חדש
      </button>
      <div className="history-title"><History size={15} /> היסטוריה</div>
      <HistoryList app={app} />
      <SidebarActions app={app} />
    </aside>
  );
}

function Brand({ onClose }: { onClose: () => void }) {
  return (
    <div className="brand">
      <span className="brand-mark"><BrandMark size={22} /></span>
      <span>
        <strong dir="ltr" className="brand-word">Sum<em>Or</em>AI</strong>
        <small>סיכום חכם עם ראיות</small>
      </span>
      <button className="mobile-close" type="button" onClick={onClose}
        aria-label="סגירת תפריט">
        <PanelRightClose size={20} />
      </button>
    </div>
  );
}

function HistoryList({ app }: { app: AppShellController }) {
  return (
    <nav className="history-list" aria-label="שיחות קודמות">
      {app.conversations.map((item) => (
        <button type="button" key={item.id}
          className={app.conversation?.id === item.id ? "active" : ""}
          onClick={() => void app.selectConversation(item.id)}>
          <Bot size={16} />
          {/* The question is what distinguishes one thread from another; a
              list of bare identifiers cannot be scanned. Older conversations
              have no title, so the identifier still leads for them. */}
          <span>
            {item.title
              ? <strong>{item.title}</strong>
              : <strong dir="ltr" title={item.root_id}>
                  {identifierLabel(item.root_id)}
                </strong>}
            <small>
              {item.title && item.root_id &&
                <span dir="ltr" title={item.root_id}>
                  {identifierLabel(item.root_id, 24)} ·{" "}
                </span>}
              {new Date(item.updated_at).toLocaleDateString("he-IL")}
            </small>
          </span>
        </button>
      ))}
      {!app.conversations.length &&
        <p className="history-empty">הסיכומים האחרונים יופיעו כאן.</p>}
    </nav>
  );
}

function SidebarActions({ app }: { app: AppShellController }) {
  return (
    <div className="sidebar-actions">
      <button type="button" onClick={() => app.setEvaluationOpen(true)}>
        <Beaker size={18} /> Evaluation
      </button>
      <button type="button" onClick={() => app.setSettingsOpen(true)}>
        <Settings size={18} /> הגדרות
      </button>
      <button className="fde-studio-action" type="button"
        onClick={() => app.setStudioOpen(true)}>
        <span className="agent-avatar"><Workflow size={18} /></span>
        <span className="nav-copy">
          <strong dir="ltr">SumOrAI Agent</strong>
          <small>Workflows, Skills וטולים</small>
        </span>
        <span className="agent-pulse" aria-hidden="true" />
      </button>
      <button type="button" onClick={() => app.setDark((value) => !value)}>
        {app.dark ? <Sun size={18} /> : <Moon size={18} />}
        {app.dark ? "מצב בהיר" : "מצב כהה"}
      </button>
    </div>
  );
}
