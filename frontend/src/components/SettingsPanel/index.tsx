"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  CheckCircle2, KeyRound, LoaderCircle, Save, Send, Settings, X,
} from "lucide-react";
import { api } from "@/services/api";

const FIELDS = [
  ["llm_model", "מודל", "text"],
  ["llm_base_url", "כתובת שרת OpenAI-compatible", "url"],
  ["openai_api_key", "מפתח API", "password"],
  ["flapi_username", "שם משתמש FLAPI", "text"],
  ["flapi_token", "טוקן FLAPI", "password"],
  ["database_url", "כתובת PostgreSQL", "text"],
  ["database_user", "משתמש PostgreSQL", "text"],
  ["database_password", "סיסמת PostgreSQL", "password"],
  ["max_parallel_workflows", "מספר תהליכים מקבילים", "number"],
  ["package_timeout_seconds", "זמן מרבי לחבילה (שניות)", "number"],
] as const;

export default function SettingsPanel({ onClose }: { onClose: () => void }) {
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");

  useEffect(() => {
    api.adminSession()
      .then(() => api.settings())
      .then((next) => {
        setValues(next);
        setAuthenticated(true);
      })
      .catch(() => setAuthenticated(false))
      .finally(() => setLoading(false));
  }, []);

  const authenticate = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.login(password);
      setValues(await api.settings());
      setPassword("");
      setAuthenticated(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ההתחברות נכשלה");
    } finally {
      setSaving(false);
    }
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      setValues(await api.updateSettings(values));
      setMessage("ההגדרות נשמרו ומוחלות על הקריאה הבאה.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "השמירה נכשלה");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal settings-modal" role="dialog" aria-modal="true">
        <header className="modal-header">
          <span className="modal-icon"><Settings size={20} /></span>
          <div><h2>הגדרות מערכת</h2><p>אותה שכבת הגדרות חיה של LocatoAI.</p></div>
          <button type="button" onClick={onClose} aria-label="סגירה"><X /></button>
        </header>
        {loading ? (
          <p className="loading-line"><LoaderCircle className="spin" /> טוען…</p>
        ) : authenticated === false ? (
          <form className="admin-login" onSubmit={authenticate}>
            <span className="login-icon"><KeyRound size={24} /></span>
            <h3>כניסת FDE</h3>
            <p>הגדרות המערכת מוגנות באותה הרשאה של Agent Studio.</p>
            <label>
              <span>סיסמה</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                autoFocus
              />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button
              className="primary-button"
              type="submit"
              disabled={saving || !password}
            >
              <Send size={17} /> {saving ? "מתחבר…" : "כניסה להגדרות"}
            </button>
          </form>
        ) : (
          <form onSubmit={save} className="settings-form">
            {FIELDS.map(([key, label, type]) => (
              <label key={key}>
                <span>{label}</span>
                <input
                  type={type}
                  value={String(values[key] ?? "")}
                  dir={key.includes("url") || key.includes("model") ? "ltr" : "auto"}
                  onChange={(event) => setValues((current) => ({
                    ...current,
                    [key]: type === "number"
                      ? Number(event.target.value)
                      : event.target.value,
                  }))}
                />
              </label>
            ))}
            {error && <p className="form-error" role="alert">{error}</p>}
            {message && (
              <p className="form-success" role="status">
                <CheckCircle2 size={16} /> {message}
              </p>
            )}
            <button className="primary-button" type="submit" disabled={saving}>
              <Save size={17} /> {saving ? "שומר…" : "שמירת הגדרות"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
