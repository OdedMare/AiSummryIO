"use client";

import { FormEvent, useEffect, useState } from "react";
import { CheckCircle2, LoaderCircle, Save, Settings, X } from "lucide-react";
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

  useEffect(() => {
    api.settings()
      .then(setValues)
      .catch((reason) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

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

