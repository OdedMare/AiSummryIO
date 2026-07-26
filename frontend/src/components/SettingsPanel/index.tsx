"use client";

import {
  CheckCircle2, KeyRound, LoaderCircle, Save, Send, Settings2, X,
} from "lucide-react";
import { SettingsContent, SettingsNavigation } from "./SettingsSections";
import type { SettingsController } from "./useSettings";
import { useSettings } from "./useSettings";

export default function SettingsPanel({ onClose }: { onClose: () => void }) {
  const settings = useSettings();
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className={`modal ${settings.authenticated ?
        "settings-workspace-modal" : "settings-modal"}`}
        role="dialog" aria-modal="true" aria-labelledby="settings-title"
        onClick={(event) => event.stopPropagation()}>
        <ModalHeader onClose={onClose} />
        <PanelContent settings={settings} />
      </section>
    </div>
  );
}

function ModalHeader({ onClose }: { onClose: () => void }) {
  return (
    <header className="modal-header">
      <span className="modal-icon"><Settings2 size={20} /></span>
      <div><h2 id="settings-title">הגדרות מערכת</h2>
        <p>ניהול מודל הבינה, שרת FLAPI, מסד הנתונים ומגבלות הריצה.</p>
      </div>
      <button type="button" onClick={onClose} aria-label="סגירת הגדרות">
        <X />
      </button>
    </header>
  );
}

function PanelContent({ settings }: { settings: SettingsController }) {
  if (settings.loading) {
    return <p className="loading-line">
      <LoaderCircle className="spin" /> טוען…
    </p>;
  }
  if (settings.authenticated === false) {
    return <Login settings={settings} />;
  }
  return <SettingsWorkspace settings={settings} />;
}

function Login({ settings }: { settings: SettingsController }) {
  return (
    <form className="admin-login" onSubmit={settings.authenticate}>
      <span className="login-icon"><KeyRound size={24} /></span>
      <h3>כניסת FDE</h3>
      <p>הגדרות המערכת מוגנות באותה הרשאה של Agent Studio.</p>
      <label><span>סיסמה</span>
        <input type="password" value={settings.password}
          onChange={(event) => settings.setPassword(event.target.value)}
          autoComplete="current-password" autoFocus />
      </label>
      {settings.error &&
        <p className="form-error" role="alert">{settings.error}</p>}
      <button className="primary-button" type="submit"
        disabled={settings.saving || !settings.password}>
        <Send size={17} /> {settings.saving ? "מתחבר…" : "כניסה להגדרות"}
      </button>
    </form>
  );
}

function SettingsWorkspace({ settings }: { settings: SettingsController }) {
  return (
    <form className="settings-workspace" onSubmit={settings.save}>
      <div className="settings-workspace-layout">
        <SettingsNavigation active={settings.activeSection}
          onChange={settings.setActiveSection} />
        <SettingsContent settings={settings} />
      </div>
      <SettingsFooter settings={settings} />
    </form>
  );
}

function SettingsFooter({ settings }: { settings: SettingsController }) {
  return (
    <footer className="settings-footer">
      {settings.error && <span className="settings-message form-error"
        role="alert">{settings.error}</span>}
      {!settings.error && settings.message &&
        <span className="settings-message form-success" role="status">
          <CheckCircle2 size={16} /> {settings.message}
        </span>}
      <button className="primary-button settings-save" type="submit"
        disabled={settings.saving}>
        <Save size={17} /> {settings.saving ? "שומר…" : "שמירת שינויים"}
      </button>
    </footer>
  );
}
