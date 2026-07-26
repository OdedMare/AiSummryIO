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
import type { Conversation, SummaryRun, SummarySkill } from "@/types";

const isActive = (run: SummaryRun | null) =>
  run?.status === "queued" || run?.status === "running";

export default function AppShell() {
  const [rootId, setRootId] = useState("");
  const [message, setMessage] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [skills, setSkills] = useState<SummarySkill[]>([]);
  const [selectedSkillKeys, setSelectedSkillKeys] = useState<string[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [run, setRun] = useState<SummaryRun | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [studioOpen, setStudioOpen] = useState(false);
  const [dark, setDark] = useState(true);
  const [notice, setNotice] = useState("");

  const loadHistory = useCallback(() => {
    api.conversations().then(setConversations).catch(() => undefined);
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem("aisummry-theme");
    const nextDark = saved ? saved === "dark" :
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = nextDark ? "dark" : "light";
    window.setTimeout(() => setDark(nextDark), 0);
    loadHistory();
    api.skills().then(setSkills).catch(() => undefined);
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
    setNotice("");
    setSelectedSkillKeys([]);
    setSidebarOpen(false);
  };

  const selectConversation = async (id: string) => {
    setError("");
    try {
      const selected = await api.conversation(id);
      setConversation(selected);
      setRootId(selected.root_id);
      const lastRun = selected.runs?.at(-1) ?? null;
      setRun(lastRun);
      setSelectedSkillKeys(lastRun?.skill_keys ?? []);
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
    setNotice("");
    try {
      if (!conversation) {
        if (!rootId.trim()) {
          const detected = message.match(
            /(?:^|\s)(?:id|מזהה)\s*[:#=-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{0,255})(?:\s|$)/i,
          );
          if (!detected) throw new Error("יש להזין מזהה בשדה או לכתוב „מזהה: …”");
          setRootId(detected[1]);
          setNotice(`זיהינו את המזהה ${detected[1]}. בדקו אותו ולחצו שוב לאישור.`);
          return;
        }
        const created = await api.start(
          rootId.trim(),
          message.trim(),
          selectedSkillKeys,
        );
        setConversation(created.conversation);
        setRun(created.run);
        loadHistory();
      } else {
        if (!message.trim()) throw new Error("יש לכתוב שאלת המשך");
        setRun(await api.followUp(
          conversation.id,
          message.trim(),
          selectedSkillKeys,
        ));
      }
      setMessage("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "הפעולה נכשלה");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleSkill = (key: string) => {
    setError("");
    setSelectedSkillKeys((current) => {
      if (current.includes(key)) {
        return current.filter((item) => item !== key);
      }
      if (current.length === 3) {
        setError("אפשר לבחור עד 3 Skills בכל סיכום");
        return current;
      }
      return [...current, key];
    });
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
            <Workflow size={18} /> מרכז ניהול
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
            <span>{conversation ? "מזהה נוכחי" : "סיכום חדש"}</span>
            <strong dir="ltr">{conversation?.root_id || "מזהה חדש"}</strong>
          </div>
          <span className="trust-indicator">
            <ShieldCheck size={16} /> מבוסס ראיות
          </span>
        </header>

        <SummaryWorkspace
          run={run}
          skills={skills}
          selectedSkillKeys={selectedSkillKeys}
          onToggleSkill={toggleSkill}
        />

        <form className="composer" onSubmit={submit}>
          {!conversation && (
            <label className="id-field">
              <span>המזהה שתרצו לסכם <b aria-hidden="true">*</b></span>
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
          {conversation ? (
            <label className="message-field">
              <span>מה עוד תרצו לדעת?</span>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="למשל: מה השתנה לאחרונה?"
                rows={2}
                disabled={submitting || isActive(run)}
              />
            </label>
          ) : (
            <details className="optional-request">
              <summary>רוצים להוסיף בקשה אישית?</summary>
              <label className="message-field">
                <span>בקשה נוספת (לא חובה)</span>
                <textarea
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder="למשל: התמקדו במידע מהשנה האחרונה"
                  rows={2}
                  disabled={submitting || isActive(run)}
                />
              </label>
            </details>
          )}
          {conversation && selectedSkillKeys.length > 0 && (
            <p className="active-skills">
              Skills פעילים:{" "}
              {skills
                .filter((skill) => selectedSkillKeys.includes(skill.content_key))
                .map((skill) => skill.name)
                .join(" · ")}
            </p>
          )}
          {error && <p className="composer-error" role="alert">{error}</p>}
          {notice && <p className="composer-notice" role="status">{notice}</p>}
          <button
            className="submit-button"
            type="submit"
            disabled={
              submitting || isActive(run) ||
              (!conversation && !rootId.trim() && !message.trim()) ||
              (!!conversation && !message.trim())
            }
          >
            <Send size={18} />
            {isActive(run) ? "מכינים את הסיכום…" :
              conversation ? "שליחת שאלה" : "סכמו עכשיו"}
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
