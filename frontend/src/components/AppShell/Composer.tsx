import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Send } from "lucide-react";
import type { SummarySkill } from "@/types";
import type { AppShellController } from "./useAppShell";
import { isActive, parseCommands } from "./useAppShell";

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
          placeholder="למשל: התמקדו במידע מהשנה האחרונה, או /תקציר מנהלים" />
      </label>
    </details>
  );
}

function FollowUpField({ app }: { app: AppShellController }) {
  return (
    <label className="message-field">
      <span>מה עוד תרצו לדעת?</span>
      <MessageInput app={app}
        placeholder="למשל: מה השתנה לאחרונה? כתבו / להפעלת Skill" />
    </label>
  );
}

type MenuAnchor = { left: number; width: number; bottom: number };

/**
 * Viewport rect for the skill menu, anchored above `element`. The menu is
 * `position: fixed` to escape the composer's scroll clipping, so it has to
 * track the textarea itself while the composer scrolls or the window resizes.
 */
function useMenuAnchor(
  element: HTMLTextAreaElement | null, active: boolean,
) {
  const [anchor, setAnchor] = useState<MenuAnchor | null>(null);

  useLayoutEffect(() => {
    if (!element || !active) { setAnchor(null); return; }
    const measure = () => {
      const rect = element.getBoundingClientRect();
      setAnchor({
        left: rect.left,
        width: rect.width,
        bottom: window.innerHeight - rect.top + 6,
      });
    };
    measure();
    window.addEventListener("resize", measure);
    // `true` captures scrolls on the composer and any other ancestor, which
    // do not bubble to `window`.
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [element, active]);

  return anchor;
}

/** The `/name` fragment being typed at the caret, or null. */
function activeQuery(value: string, caret: number) {
  const before = value.slice(0, caret);
  const match = before.match(/(?:^|\s)\/([^/\n]*)$/);
  return match ? match[1] : null;
}

function MessageInput({
  app,
  placeholder,
}: {
  app: AppShellController;
  placeholder: string;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);
  const [field, setField] = useState<HTMLTextAreaElement | null>(null);
  const [caret, setCaret] = useState(0);
  const [open, setOpen] = useState(false);
  const query = open ? activeQuery(app.message, caret) : null;
  const matches = useMemo(
    () => filterSkills(app.skills, query), [app.skills, query]);
  const showMenu = query !== null && !!matches.length;
  const anchor = useMenuAnchor(field, showMenu);

  const sync = (element: HTMLTextAreaElement) => {
    setCaret(element.selectionStart ?? 0); setOpen(true);
  };

  const complete = (skill: SummarySkill) => {
    const before = app.message.slice(0, caret).replace(/\/[^/\n]*$/, "");
    const next = `${before}/${skill.name} ${app.message.slice(caret)}`;
    app.setMessage(next); setOpen(false);
    const position = before.length + skill.name.length + 2;
    window.requestAnimationFrame(() => {
      ref.current?.focus();
      ref.current?.setSelectionRange(position, position);
    });
  };

  return (
    <div className="message-input">
      <textarea
        ref={(node) => { ref.current = node; setField(node); }}
        value={app.message}
        onChange={(event) => {
          app.setMessage(event.target.value); sync(event.target);
        }}
        onKeyUp={(event) => sync(event.currentTarget)}
        onClick={(event) => sync(event.currentTarget)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && query !== null) {
            event.stopPropagation(); setOpen(false);
          }
        }}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        placeholder={placeholder} rows={2}
        disabled={app.submitting || isActive(app.run)} />
      {showMenu && !!anchor && createPortal(
        <SkillMenu matches={matches} anchor={anchor} onPick={complete} />,
        document.body)}
    </div>
  );
}

function filterSkills(skills: SummarySkill[], query: string | null) {
  if (query === null) return [];
  const wanted = query.trim().toLowerCase();
  if (!wanted) return skills;
  return skills.filter((skill) =>
    skill.name.toLowerCase().includes(wanted) ||
    skill.content_key.toLowerCase().includes(wanted));
}

function SkillMenu({
  matches, anchor, onPick,
}: {
  matches: SummarySkill[];
  anchor: MenuAnchor;
  onPick: (skill: SummarySkill) => void;
}) {
  return (
    <ul className="skill-menu" role="listbox" aria-label="Skills זמינים"
      style={{
        left: anchor.left, width: anchor.width, bottom: anchor.bottom,
      }}>
      {matches.map((skill) =>
        <li key={skill.content_key} role="option" aria-selected="false">
          <button type="button" onMouseDown={(event) => event.preventDefault()}
            onClick={() => onPick(skill)}>
            <strong className="skill-command">/{skill.name}</strong>
            <small>{skill.description}</small>
          </button>
        </li>)}
    </ul>
  );
}

function ActiveSkills({ app }: { app: AppShellController }) {
  const names = useMemo(() => {
    const { keys } = parseCommands(app.message, app.skills);
    return app.skills.filter((skill) => keys.includes(skill.content_key))
      .map((skill) => skill.name).join(" · ");
  }, [app.message, app.skills]);
  if (!names) return null;
  return <p className="active-skills">Skills שיופעלו: {names}</p>;
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
