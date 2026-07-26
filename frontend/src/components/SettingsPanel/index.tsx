"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  Bot, CheckCircle2, Database, KeyRound, LoaderCircle, RefreshCw, Save, Send,
  ServerCog, Settings2, Timer, X,
} from "lucide-react";
import { api } from "@/services/api";

type SettingsSection = "agent" | "flapi" | "database" | "limits";

const SETTINGS_SECTIONS = [
  {
    id: "agent" as const,
    label: "סוכן ומודל",
    description: "מודל, כתובת בסיס ומפתח API",
    icon: Bot,
  },
  {
    id: "flapi" as const,
    label: "שרת FLAPI",
    description: "הרשאות חבילות התהליך",
    icon: ServerCog,
  },
  {
    id: "database" as const,
    label: "מסד הנתונים",
    description: "חיבור PostgreSQL וסכמה",
    icon: Database,
  },
  {
    id: "limits" as const,
    label: "מגבלות ושמירה",
    description: "מקביליות, פסקי זמן ושמירת מידע",
    icon: Timer,
  },
];

const MASKED = "********";

export default function SettingsPanel({ onClose }: { onClose: () => void }) {
  const [activeSection, setActiveSection] = useState<SettingsSection>("agent");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState("");

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
    setMessage("");
    try {
      setValues(await api.updateSettings(values));
      setMessage("ההגדרות נשמרו ומוחלות על הקריאה הבאה.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "השמירה נכשלה");
    } finally {
      setSaving(false);
    }
  };

  const loadModels = async () => {
    setLoadingModels(true);
    setModelsError("");
    try {
      setModels((await api.models()).models);
    } catch (reason) {
      setModelsError(
        reason instanceof Error ? reason.message : "טעינת המודלים נכשלה",
      );
    } finally {
      setLoadingModels(false);
    }
  };

  const set = (key: string, value: unknown) =>
    setValues((current) => ({ ...current, [key]: value }));

  const text = (key: string) => String(values[key] ?? "");
  const checked = (key: string) => Boolean(values[key]);
  /** The backend masks secrets; an empty box keeps the stored value. */
  const secretSaved = (key: string) => values[key] === MASKED;

  const field = (
    key: string,
    label: string,
    props: {
      type?: string;
      optional?: string;
      placeholder?: string;
      ltr?: boolean;
      list?: string;
      min?: string;
      max?: string;
    } = {},
  ) => {
    const isSecret = props.type === "password";
    return (
      <>
        <label className="field-label" htmlFor={`set-${key}`}>
          {label}
          {props.optional && <span className="optional"> ({props.optional})</span>}
          {isSecret && secretSaved(key) && <span className="key-hint"> (נשמר)</span>}
        </label>
        <input
          id={`set-${key}`}
          className="settings-input"
          type={props.type ?? "text"}
          dir={props.ltr === false ? "auto" : "ltr"}
          list={props.list}
          min={props.min}
          max={props.max}
          placeholder={
            isSecret && secretSaved(key)
              ? "השאירו ריק כדי לשמור את הערך הנוכחי"
              : props.placeholder
          }
          value={isSecret && secretSaved(key) ? "" : text(key)}
          onChange={(event) =>
            set(
              key,
              props.type === "number"
                ? event.target.value === "" ? null : Number(event.target.value)
                : event.target.value,
            )
          }
        />
      </>
    );
  };

  const toggle = (key: string, label: string, optional?: string) => (
    <label className="field-label">
      <input
        type="checkbox"
        checked={checked(key)}
        onChange={(event) => set(key, event.target.checked)}
      />
      {label}
      {optional && <span className="optional"> ({optional})</span>}
    </label>
  );

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className={`modal ${authenticated ? "settings-workspace-modal" : "settings-modal"}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <span className="modal-icon"><Settings2 size={20} /></span>
          <div>
            <h2 id="settings-title">הגדרות מערכת</h2>
            <p>ניהול מודל הבינה, שרת FLAPI, מסד הנתונים ומגבלות הריצה.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="סגירת הגדרות">
            <X />
          </button>
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
          <form className="settings-workspace" onSubmit={save}>
            <div className="settings-workspace-layout">
              <nav className="settings-nav" aria-label="קטגוריות הגדרות">
                <p className="settings-nav-label">קטגוריות</p>
                {SETTINGS_SECTIONS.map(({ id, label, description, icon: Icon }) => (
                  <button
                    key={id}
                    type="button"
                    className={activeSection === id ? "active" : ""}
                    onClick={() => setActiveSection(id)}
                    aria-current={activeSection === id ? "page" : undefined}
                  >
                    <Icon size={18} />
                    <span>
                      <strong>{label}</strong>
                      <small>{description}</small>
                    </span>
                  </button>
                ))}
              </nav>

              <div className="settings-content">
                {activeSection === "agent" && (
                  <section className="settings-section">
                    <h3>מודל בינה מלאכותית</h3>
                    {field("openai_api_key", "מפתח API", {
                      type: "password",
                      optional: "לא נדרש לשרתים מקומיים כמו Ollama",
                      placeholder: "sk-…",
                    })}
                    <div className="model-field-header">
                      <label className="field-label" htmlFor="set-llm_model">מודל</label>
                      <button
                        type="button"
                        className="models-refresh"
                        onClick={() => void loadModels()}
                        disabled={loadingModels}
                      >
                        <RefreshCw className={loadingModels ? "spin" : ""} size={14} />
                        {loadingModels ? "טוען…" : "רענון מודלים"}
                      </button>
                    </div>
                    <input
                      id="set-llm_model"
                      className="settings-input"
                      dir="ltr"
                      list="available-models"
                      placeholder="gpt-4o-mini"
                      value={text("llm_model")}
                      onChange={(event) => set("llm_model", event.target.value)}
                    />
                    <datalist id="available-models">
                      {models.map((model) => <option key={model} value={model} />)}
                    </datalist>
                    {models.length > 0 && (
                      <p className="models-status">נמצאו {models.length} מודלים זמינים</p>
                    )}
                    {modelsError && (
                      <p className="models-status error" role="alert" dir="auto">
                        {modelsError}
                      </p>
                    )}
                    {field("llm_base_url", "כתובת בסיס", {
                      type: "url",
                      optional: "שרת תואם OpenAI; ריק = OpenAI",
                      placeholder: "http://localhost:11434/v1",
                    })}
                    {toggle(
                      "llm_diet_mode",
                      "מצב חסכוני בטוקנים",
                      "הנחיות קצרות ופלט מוגבל",
                    )}
                  </section>
                )}

                {activeSection === "flapi" && (
                  <section className="settings-section">
                    <h3>שרת FLAPI</h3>
                    {field("flapi_username", "שם משתמש FLAPI", {
                      placeholder: "network username",
                    })}
                    {field("flapi_token", "אסימון הרשאה", {
                      type: "password",
                      placeholder: "Authorization token",
                    })}
                    {toggle("flapi_verify_tls", "אימות תעודת TLS")}
                    <p className="models-status" dir="auto">
                      חבילות תהליך מזוהות לפי מזהה חבילה בקטלוג הכלים.
                    </p>
                  </section>
                )}

                {activeSection === "database" && (
                  <section className="settings-section">
                    <h3>מסד הנתונים (PostgreSQL)</h3>
                    {field("database_url", "כתובת חיבור מלאה", {
                      optional: "ברירת מחדל לשדות הריקים",
                      placeholder: "postgresql://localhost:5432/aisummry",
                    })}
                    <div className="settings-input-row">
                      <div>
                        {field("database_host", "שרת", { placeholder: "localhost" })}
                      </div>
                      <div>
                        {field("database_port", "פורט", {
                          type: "number",
                          min: "1",
                          max: "65535",
                          placeholder: "5432",
                        })}
                      </div>
                    </div>
                    {field("database_name", "שם מסד הנתונים", {
                      placeholder: "aisummry",
                    })}
                    <div className="settings-input-row">
                      <div>
                        {field("database_user", "שם משתמש", { placeholder: "postgres" })}
                      </div>
                      <div>
                        {field("database_password", "סיסמה", {
                          type: "password",
                          placeholder: "סיסמה",
                        })}
                      </div>
                    </div>
                    {field("database_schema", "סכמה", {
                      optional: "אותיות, ספרות וקו תחתון בלבד",
                      placeholder: "public",
                    })}
                  </section>
                )}

                {activeSection === "limits" && (
                  <section className="settings-section">
                    <h3>מגבלות ריצה ושמירת מידע</h3>
                    {field("max_parallel_workflows", "מספר תהליכים מקבילים", {
                      type: "number",
                      min: "1",
                      placeholder: "4",
                    })}
                    {field("package_timeout_seconds", "זמן מרבי לחבילה", {
                      type: "number",
                      min: "1",
                      optional: "שניות",
                      placeholder: "120",
                    })}
                    {field("conversation_retention_days", "שמירת שיחות וראיות", {
                      type: "number",
                      min: "1",
                      optional: "ימים",
                      placeholder: "30",
                    })}
                    {field("log_retention_days", "שמירת לוגים", {
                      type: "number",
                      min: "1",
                      optional: "ימים",
                      placeholder: "14",
                    })}
                  </section>
                )}
              </div>
            </div>

            <footer className="settings-footer">
              {error && (
                <span className="settings-message form-error" role="alert">{error}</span>
              )}
              {!error && message && (
                <span className="settings-message form-success" role="status">
                  <CheckCircle2 size={16} /> {message}
                </span>
              )}
              <button className="primary-button settings-save" type="submit" disabled={saving}>
                <Save size={17} /> {saving ? "שומר…" : "שמירת שינויים"}
              </button>
            </footer>
          </form>
        )}
      </section>
    </div>
  );
}
