"use client";

import {
  AlertTriangle, CheckCircle2, LoaderCircle, Save, Settings2, X,
} from "lucide-react";
import { SettingsContent, SettingsNavigation } from "./SettingsSections";
import type { SettingsController } from "./useSettings";
import { useSettings } from "./useSettings";

export default function SettingsPanel({ onClose }: { onClose: () => void }) {
  const settings = useSettings();
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className={`modal ${settings.authorized ?
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
  if (settings.authorized === false) {
    return <p className="form-error" role="alert">
      <AlertTriangle size={18} /> אין הרשאת FDE. יש להגדיר טוקן API תקין בשרת.
    </p>;
  }
  return <SettingsWorkspace settings={settings} />;
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
