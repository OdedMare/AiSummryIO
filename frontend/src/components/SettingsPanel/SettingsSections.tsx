import {
  Bot, Database, RefreshCw, ServerCog, Timer,
} from "lucide-react";
import { SettingsField as Field, SettingsToggle as Toggle } from "./SettingsField";
import type { SettingsController, SettingsSection } from "./useSettings";

const SECTIONS = [
  { id: "agent" as const, label: "סוכן ומודל",
    description: "מודל, כתובת בסיס ומפתח API", icon: Bot },
  { id: "flapi" as const, label: "שרת FLAPI",
    description: "הרשאות חבילות התהליך", icon: ServerCog },
  { id: "database" as const, label: "מסד הנתונים",
    description: "חיבור PostgreSQL וסכמה", icon: Database },
  { id: "limits" as const, label: "מגבלות ושמירה",
    description: "מקביליות, פסקי זמן ושמירת מידע", icon: Timer },
];

export function SettingsNavigation({
  active,
  onChange,
}: {
  active: SettingsSection;
  onChange: (section: SettingsSection) => void;
}) {
  return (
    <nav className="settings-nav" aria-label="קטגוריות הגדרות">
      <p className="settings-nav-label">קטגוריות</p>
      {SECTIONS.map(({ id, label, description, icon: Icon }) => (
        <button key={id} type="button"
          className={active === id ? "active" : ""}
          onClick={() => onChange(id)}
          aria-current={active === id ? "page" : undefined}>
          <Icon size={18} />
          <span><strong>{label}</strong><small>{description}</small></span>
        </button>
      ))}
    </nav>
  );
}

export function SettingsContent({ settings }: { settings: SettingsController }) {
  const sections = {
    agent: <AgentSettings settings={settings} />,
    flapi: <FlapiSettings settings={settings} />,
    database: <DatabaseSettings settings={settings} />,
    limits: <LimitSettings settings={settings} />,
  };
  return <div className="settings-content">{sections[settings.activeSection]}</div>;
}

function AgentSettings({ settings }: { settings: SettingsController }) {
  return (
    <section className="settings-section">
      <h3>מודל בינה מלאכותית</h3>
      <Field settings={settings} name="openai_api_key" label="מפתח API"
        type="password" optional="לא נדרש לשרתים מקומיים כמו Ollama"
        placeholder="sk-…" />
      <ModelField settings={settings} />
      <Field settings={settings} name="llm_base_url" label="כתובת בסיס"
        type="url" optional="שרת תואם OpenAI; ריק = OpenAI"
        placeholder="http://localhost:11434/v1" />
      <Toggle settings={settings} name="llm_diet_mode"
        label="מצב חסכוני בטוקנים" optional="הנחיות קצרות ופלט מוגבל" />
    </section>
  );
}

function ModelField({ settings }: { settings: SettingsController }) {
  return (
    <>
      <div className="model-field-header">
        <label className="field-label" htmlFor="set-llm_model">מודל</label>
        <button type="button" className="models-refresh"
          onClick={() => void settings.loadModels()}
          disabled={settings.loadingModels}>
          <RefreshCw className={settings.loadingModels ? "spin" : ""} size={14} />
          {settings.loadingModels ? "טוען…" : "רענון מודלים"}
        </button>
      </div>
      <input id="set-llm_model" className="settings-input" dir="ltr"
        list="available-models" placeholder="gpt-4o-mini"
        value={settings.text("llm_model")}
        onChange={(event) => settings.set("llm_model", event.target.value)} />
      <datalist id="available-models">
        {settings.models.map((model) => <option key={model} value={model} />)}
      </datalist>
      <ModelStatus settings={settings} />
    </>
  );
}

function ModelStatus({ settings }: { settings: SettingsController }) {
  if (settings.modelsError) {
    return <p className="models-status error" role="alert" dir="auto">
      {settings.modelsError}
    </p>;
  }
  if (!settings.models.length) return null;
  return <p className="models-status">
    נמצאו {settings.models.length} מודלים זמינים
  </p>;
}

function FlapiSettings({ settings }: { settings: SettingsController }) {
  return (
    <section className="settings-section">
      <h3>שרת FLAPI</h3>
      <Field settings={settings} name="flapi_username"
        label="שם משתמש FLAPI" placeholder="network username" />
      <Field settings={settings} name="flapi_token" label="אסימון הרשאה"
        type="password" placeholder="Authorization token" />
      <Toggle settings={settings} name="flapi_verify_tls"
        label="אימות תעודת TLS" />
      <p className="models-status" dir="auto">
        חבילות תהליך מזוהות לפי מזהה חבילה בקטלוג הכלים.
      </p>
    </section>
  );
}

function DatabaseSettings({ settings }: { settings: SettingsController }) {
  return (
    <section className="settings-section">
      <h3>מסד הנתונים (PostgreSQL)</h3>
      <Field settings={settings} name="database_url" label="כתובת חיבור מלאה"
        optional="ברירת מחדל לשדות הריקים"
        placeholder="postgresql://localhost:5432/aisummry" />
      <div className="settings-input-row">
        <div><Field settings={settings} name="database_host" label="שרת"
          placeholder="localhost" /></div>
        <div><Field settings={settings} name="database_port" label="פורט"
          type="number" min="1" max="65535" placeholder="5432" /></div>
      </div>
      <Field settings={settings} name="database_name" label="שם מסד הנתונים"
        placeholder="aisummry" />
      <div className="settings-input-row">
        <div><Field settings={settings} name="database_user" label="שם משתמש"
          placeholder="postgres" /></div>
        <div><Field settings={settings} name="database_password" label="סיסמה"
          type="password" placeholder="סיסמה" /></div>
      </div>
      <Field settings={settings} name="database_schema" label="סכמה"
        optional="אותיות, ספרות וקו תחתון בלבד" placeholder="public" />
    </section>
  );
}

function LimitSettings({ settings }: { settings: SettingsController }) {
  return (
    <section className="settings-section">
      <h3>מגבלות ריצה ושמירת מידע</h3>
      <Field settings={settings} name="max_parallel_workflows"
        label="מספר תהליכים מקבילים" type="number" min="1" placeholder="4" />
      <Field settings={settings} name="package_timeout_seconds"
        label="זמן מרבי לחבילה" type="number" min="1" optional="שניות"
        placeholder="120" />
      <Field settings={settings} name="llm_timeout_seconds"
        label="זמן מרבי לתשובת המודל" type="number" min="1" optional="שניות"
        placeholder="120" />
      <Field settings={settings} name="conversation_retention_days"
        label="שמירת שיחות וראיות" type="number" min="1" optional="ימים"
        placeholder="30" />
      <Field settings={settings} name="log_retention_days" label="שמירת לוגים"
        type="number" min="1" optional="ימים" placeholder="14" />
    </section>
  );
}
