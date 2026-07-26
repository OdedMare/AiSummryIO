import { Send } from "lucide-react";
import type { AppShellController } from "./useAppShell";
import { isActive } from "./useAppShell";

export default function Composer({ app }: { app: AppShellController }) {
  return (
    <form className="composer" onSubmit={app.submit}>
      {!app.conversation && <IdentifierField app={app} />}
      <MessageField app={app} />
      <ActiveSkills app={app} />
      {app.error && <p className="composer-error" role="alert">{app.error}</p>}
      {app.notice &&
        <p className="composer-notice" role="status">{app.notice}</p>}
      <SubmitButton app={app} />
    </form>
  );
}

function IdentifierField({ app }: { app: AppShellController }) {
  return (
    <label className="id-field">
      <span>המזהה שתרצו לסכם <b aria-hidden="true">*</b></span>
      <input value={app.rootId}
        onChange={(event) => app.setRootId(event.target.value)}
        placeholder="לדוגמה: HOME-ABC-001" dir="ltr" autoComplete="off"
        maxLength={256} disabled={app.submitting} />
    </label>
  );
}

function MessageField({ app }: { app: AppShellController }) {
  if (app.conversation) return <FollowUpField app={app} />;
  return (
    <details className="optional-request">
      <summary>רוצים להוסיף בקשה אישית?</summary>
      <label className="message-field">
        <span>בקשה נוספת (לא חובה)</span>
        <MessageInput app={app}
          placeholder="למשל: התמקדו במידע מהשנה האחרונה" />
      </label>
    </details>
  );
}

function FollowUpField({ app }: { app: AppShellController }) {
  return (
    <label className="message-field">
      <span>מה עוד תרצו לדעת?</span>
      <MessageInput app={app} placeholder="למשל: מה השתנה לאחרונה?" />
    </label>
  );
}

function MessageInput({
  app,
  placeholder,
}: {
  app: AppShellController;
  placeholder: string;
}) {
  return (
    <textarea value={app.message}
      onChange={(event) => app.setMessage(event.target.value)}
      placeholder={placeholder} rows={2}
      disabled={app.submitting || isActive(app.run)} />
  );
}

function ActiveSkills({ app }: { app: AppShellController }) {
  if (!app.conversation || !app.selectedSkillKeys.length) return null;
  const names = app.skills
    .filter((skill) => app.selectedSkillKeys.includes(skill.content_key))
    .map((skill) => skill.name).join(" · ");
  return <p className="active-skills">Skills פעילים: {names}</p>;
}

function SubmitButton({ app }: { app: AppShellController }) {
  const active = isActive(app.run);
  const disabled = app.submitting || active ||
    (!app.conversation && !app.rootId.trim() && !app.message.trim()) ||
    (!!app.conversation && !app.message.trim());
  const label = active ? "מכינים את הסיכום…" :
    app.conversation ? "שליחת שאלה" : "סכמו עכשיו";
  return (
    <button className="submit-button" type="submit" disabled={disabled}>
      <Send size={18} />{label}
    </button>
  );
}
