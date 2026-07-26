"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  Bot, History, Menu, Moon, PanelRightClose, Plus, Send,
  Settings, ShieldCheck, Sparkles, Sun, Workflow,
} from "lucide-react";
import AgentStudioPanel from "@/components/AgentStudioPanel";
import SettingsPanel from "@/components/SettingsPanel";
import SummaryWorkspace from "@/components/SummaryWorkspace";
import { api } from "@/services/api";
import type { Conversation, SummaryRun } from "@/types";

const isActive = (run: SummaryRun | null) =>
  run?.status === "queued" || run?.status === "running";

export default function AppShell() {
  const [rootId, setRootId] = useState("");
  const [message, setMessage] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [run, setRun] = useState<SummaryRun | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [studioOpen, setStudioOpen] = useState(false);
  const [dark, setDark] = useState(true);

  const loadHistory = useCallback(() => {
    api.conversations().then(setConversations).catch(() => undefined);
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem("aisummry-theme");
    const nextDark = saved ? saved === "dark" :
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    setDark(nextDark);
    document.documentElement.dataset.theme = nextDark ? "dark" : "light";
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.localStorage.setItem("aisummry-theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    if (!run || !isActive(run)) return;
    const timer = window.setInterval(() => {
      api.run(run.id).then((next) => {
        setRun(next);
        if (!isActive(next)) loadHistory();
      }).catch((reason) => setError(reason.message));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [run, loadHistory]);

  const startNew = () => {
    setConversation(null);
    setRun(null);
    setRootId("");
    setMessage("");
    setError("");
    setSidebarOpen(false);
  };

  const selectConversation = async (id: string) => {
    setError("");
    try {
      const selected = await api.conversation(id);
      setConversation(selected);
      setRootId(selected.root_id);
      setRun(selected.runs?.at(-1) ?? null);
      setSidebarOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "לא ניתן לטעון שיחה");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting || isActive(run)) return;
    setSubmitting(true);
    setError("");
    try {
      if (!conversation) {
        if (!rootId.trim()) throw new Error("יש להזין מזהה");
        const created = await api.start(rootId.trim(), message.trim());
        setConversation(created.conversation);
        setRun(created.run);
        loadHistory();
      } else {
        if (!message.trim()) throw new Error("יש לכתוב שאלת המשך");
        setRun(await api.followUp(conversation.id, message.trim()));
      }
      setMessage("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "הפעולה נכשלה");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand">
          <span className="brand-mark"><Sparkles size={20} /></span>
          <span><strong>AiSummryIO</strong><small>סיכום חכם עם ראיות</small></span>
          <button
            className="mobile-close"
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label="סגירת תפריט"
          >
            <PanelRightClose size={20} />
          </button>
        </div>
        <button className="new-summary" type="button" onClick={startNew}>
          <Plus size={18} /> סיכום חדש
        </button>
        <div className="history-title"><History size={15} /> היסטוריה</div>
        <nav className="history-list" aria-label="שיחות קודמות">
          {conversations.map((item) => (
            <button
              type="button"
              key={item.id}
              className={conversation?.id === item.id ? "active" : ""}
              onClick={() => void selectConversation(item.id)}
            >
              <Bot size={16} />
              <span>
                <strong dir="ltr">{item.root_id}</strong>
                <small>
                  {new Date(item.updated_at).toLocaleDateString("he-IL")}
                </small>
              </span>
            </button>
          ))}
          {!conversations.length && (
            <p className="history-empty">הסיכומים האחרונים יופיעו כאן.</p>
          )}
        </nav>
        <div className="sidebar-actions">
          <button type="button" onClick={() => setSettingsOpen(true)}>
            <Settings size={18} /> הגדרות
          </button>
          <button type="button" onClick={() => setStudioOpen(true)}>
            <Workflow size={18} /> Agent Studio
          </button>
          <button type="button" onClick={() => setDark((value) => !value)}>
            {dark ? <Sun size={18} /> : <Moon size={18} />}
            {dark ? "מצב בהיר" : "מצב כהה"}
          </button>
        </div>
      </aside>

      <section className="conversation-shell">
        <header className="topbar">
          <button
            className="menu-button"
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="פתיחת תפריט"
          >
            <Menu size={21} />
          </button>
          <div>
            <span>סיכום פעיל</span>
            <strong dir="ltr">{conversation?.root_id || "מזהה חדש"}</strong>
          </div>
          <span className="trust-indicator">
            <ShieldCheck size={16} /> מבוסס ראיות
          </span>
        </header>

        <SummaryWorkspace run={run} />

        <form className="composer" onSubmit={submit}>
          {!conversation && (
            <label className="id-field">
              <span>מזהה לסיכום <b aria-hidden="true">*</b></span>
              <input
                value={rootId}
                onChange={(event) => setRootId(event.target.value)}
                placeholder="לדוגמה: HOME-ABC-001"
                dir="ltr"
                autoComplete="off"
                maxLength={256}
                disabled={submitting}
              />
            </label>
          )}
          <label className="message-field">
            <span>
              {conversation ? "שאלת המשך" : "בקשה נוספת (לא חובה)"}
            </span>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder={conversation
                ? "במה תרצו להעמיק?"
                : "למשל: סכם את הסיכונים והקשרים החשובים"}
              rows={2}
              disabled={submitting || isActive(run)}
            />
          </label>
          {error && <p className="composer-error" role="alert">{error}</p>}
          <button
            className="submit-button"
            type="submit"
            disabled={
              submitting || isActive(run) ||
              (!conversation && !rootId.trim()) ||
              (!!conversation && !message.trim())
            }
          >
            <Send size={18} />
            {isActive(run) ? "התהליכים עובדים…" :
              conversation ? "שליחת שאלה" : "יצירת סיכום מלא"}
          </button>
        </form>
      </section>

      {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}
      {studioOpen && <AgentStudioPanel onClose={() => setStudioOpen(false)} />}
      {sidebarOpen && (
        <button
          className="sidebar-backdrop"
          type="button"
          onClick={() => setSidebarOpen(false)}
          aria-label="סגירת תפריט"
        />
      )}
    </div>
  );
}

