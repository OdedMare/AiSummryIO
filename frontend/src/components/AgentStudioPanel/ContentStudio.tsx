"use client";

import { FormEvent, useState } from "react";
import {
  Beaker, BookOpen, LoaderCircle, Save, Send, Sparkles,
} from "lucide-react";
import { api } from "@/services/api";
import type {
  AgentContent, SkillPreviewResult,
} from "@/types";

const emptyContent = {
  content_key: "", kind: "skill", name: "", description: "", content: "",
  user_selectable: true,
};

const sampleSections =
  `בעלות | נמצאה בעלות רשומה | דנה כהן רשומה כבעלים משנת 2019
שעבודים | נמצא שעבוד פעיל | שעבוד לטובת בנק המזרחי נרשם ב-2021
היתרים | נמצאה בקשה שסורבה | בקשת היתר מ-2023 סורבה`;

export default function ContentStudio({
  items, onRefresh,
}: {
  items: AgentContent[];
  onRefresh: () => Promise<void>;
}) {
  const [form, setForm] = useState(emptyContent);
  /* Which item this form is editing, or "" for a new one. A Skill or prompt
     is one row now rather than a stack of versions, so saving an edit updates
     that row and a published Skill stays published through it. */
  const [editingId, setEditingId] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const edit = (item: AgentContent) => {
    setEditingId(item.id); setError("");
    setForm({
      content_key: item.content_key, kind: item.kind, name: item.name,
      description: item.description, content: item.content,
      user_selectable: item.user_selectable,
    });
  };
  const reset = () => { setForm(emptyContent); setEditingId(""); };
  const update = (patch: Partial<typeof emptyContent>) =>
    setForm((current) => ({ ...current, ...patch }));
  const save = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const payload = {
        ...form, content_key: form.content_key || undefined,
        user_selectable: form.kind === "skill" && form.user_selectable,
      };
      if (editingId) await api.updateContent(editingId, payload);
      else { await api.createContent(payload); reset(); }
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "השמירה נכשלה");
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="studio-split">
      <ContentList items={items} onEdit={edit} onRefresh={onRefresh} />
      <ContentForm form={form} update={update} save={save} error={error}
        saving={saving} editing={!!editingId} reset={reset} />
    </div>
  );
}

function ContentList({
  items, onEdit, onRefresh,
}: {
  items: AgentContent[];
  onEdit: (item: AgentContent) => void;
  onRefresh: () => Promise<void>;
}) {
  return (
    <section className="studio-list">
      <header><h3>Skills והנחיות</h3><span>{items.length} פריטים</span></header>
      {items.map((item) => <ContentCard key={item.id} item={item}
        onEdit={onEdit} onRefresh={onRefresh} />)}
    </section>
  );
}

function ContentCard({
  item, onEdit, onRefresh,
}: {
  item: AgentContent;
  onEdit: (item: AgentContent) => void;
  onRefresh: () => Promise<void>;
}) {
  const Icon = item.kind === "skill" ? BookOpen : Sparkles;
  return (
    <article className="content-card">
      <button type="button" onClick={() => onEdit(item)}>
        <span><Icon size={17} /></span><span><strong>{item.name}</strong>
          <small>{item.kind === "skill" ? "Skill" : "הנחיית מערכת"}{" · "}
            {item.status === "published" ? "פורסם" : "טיוטה"}
            {item.user_selectable ? " · מוצג למשתמשים" : ""}
          </small>
        </span>
      </button>
      {item.status !== "published" && <button type="button"
        onClick={() => void api.publishContent(item.id).then(onRefresh)}>
        <Send size={15} /> פרסום
      </button>}
    </article>
  );
}

function ContentForm({
  form, update, save, error, saving, editing, reset,
}: {
  form: typeof emptyContent;
  update: (patch: Partial<typeof emptyContent>) => void;
  save: (event: FormEvent) => Promise<void>;
  error: string;
  saving: boolean;
  editing: boolean;
  reset: () => void;
}) {
  return (
    <form className="studio-form" onSubmit={save}>
      <header><span><BookOpen size={19} /></span><div>
        <h3>{editing ? "עריכת Skill או הנחיה" : "Skill או הנחיה חדשים"}</h3>
        <p>Skill שמוצג למשתמש באמת משנה את תוצאת הסיכום.</p>
      </div></header>
      <div className="form-grid two">
        <label><span>סוג</span><select value={form.kind}
          onChange={(e) => update({ kind: e.target.value })}>
          <option value="skill">Skill לסיכום</option>
          <option value="prompt">הנחיית מערכת</option>
        </select></label>
        <label><span>שם *</span><input value={form.name}
          onChange={(e) => update({ name: e.target.value })} /></label>
      </div>
      <label><span>מה המשתמש יקבל?</span><input value={form.description}
        onChange={(e) => update({ description: e.target.value })} /></label>
      {form.kind === "skill" && <SelectableToggle form={form} update={update} />}
      <label><span>הוראות הפעלה אמיתיות</span>
        <textarea className="content-editor" value={form.content}
          onChange={(e) => update({ content: e.target.value })} rows={18} />
      </label>
      {form.kind === "skill" && form.content.trim() &&
        <SkillTester name={form.name} content={form.content} />}
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="form-actions">
        {editing && <button type="button" className="secondary-button"
          onClick={reset}>ביטול</button>}
        <button className="primary-button" type="submit"
          disabled={saving || !form.name || !form.content}>
          <Save size={17} /> {editing ? "שמירת שינויים" : "שמירת טיוטה"}
        </button>
      </div>
    </form>
  );
}

function SelectableToggle({
  form, update,
}: {
  form: typeof emptyContent;
  update: (patch: Partial<typeof emptyContent>) => void;
}) {
  return (
    <label className="agent-tool-toggle">
      <input type="checkbox" checked={form.user_selectable}
        onChange={(e) => update({ user_selectable: e.target.checked })} />
      <span>הצגה במסך הסיכום
        <small>המשתמש יוכל לבחור את ה־Skill והתוצאה תופיע בנפרד.</small>
      </span>
    </label>
  );
}

function SkillTester({ name, content }: { name: string; content: string }) {
  const [question, setQuestion] = useState("מה חשוב לדעת על המזהה?");
  const [sections, setSections] = useState(sampleSections);
  const [result, setResult] = useState<SkillPreviewResult | null>(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const run = async () => {
    setRunning(true); setError(""); setResult(null);
    try {
      setResult(await api.previewSkill({
        name: name || "טיוטת Skill", content, question,
        sections: parseSections(sections),
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "הבדיקה נכשלה");
    } finally {
      setRunning(false);
    }
  };
  return (
    <section className="skill-tester">
      <header><span><Beaker size={17} /></span><div>
        <h4>בדיקת ה־Skill</h4>
        <p>מריץ רק את ה־Skill על חלקי סיכום לדוגמה. שום דבר לא נשמר.</p>
      </div></header>
      <label><span>שאלת המשתמש</span><input value={question}
        onChange={(event) => setQuestion(event.target.value)} /></label>
      <label><span>חלקי סיכום לדוגמה</span><textarea value={sections}
        onChange={(event) => setSections(event.target.value)} rows={4} />
        <small>שורה לכל חלק: שם | סיכום | עובדה | עובדה…</small>
      </label>
      <button type="button" className="secondary-button"
        onClick={() => void run()}
        disabled={running || !content.trim() || !sections.trim()}>
        {running ? <LoaderCircle className="spin" size={16} /> :
          <Beaker size={16} />}
        {running ? " מריץ…" : " הרצת בדיקה"}
      </button>
      {error && <p className="form-error" role="alert">{error}</p>}
      {result && <SkillTestResult result={result} />}
    </section>
  );
}

function SkillTestResult({ result }: { result: SkillPreviewResult }) {
  return (
    <article className="skill-tester-result">
      <h5>{result.result.name}</h5><p>{result.result.summary}</p>
      {!!result.result.items.length &&
        <ul>{result.result.items.map((item) => <li key={item}>{item}</li>)}</ul>}
      <p className="skill-tester-sources">מקורות שאושרו:{" "}
        {result.result.sources.length ? result.result.sources.join(", ") : "אין"}
      </p>
      {!!result.dropped_sources.length &&
        <p className="form-error" role="alert">
          מקורות שנדחו כי אינם קיימים בחלקי הסיכום:{" "}
          {result.dropped_sources.join(", ")}. יש לחדד ב־Skill שיצטט רק שמות
          של חלקים שסופקו.
        </p>}
    </article>
  );
}

function parseSections(value: string) {
  return value.split("\n")
    .map((line) => line.split("|").map((part) => part.trim()))
    .filter((parts) => parts[0])
    .map((parts, index) => ({
      workflow_key: `sample-${index + 1}`, name: parts[0],
      status: "completed", summary: parts[1] ?? "",
      facts: parts.slice(2).filter(Boolean), warnings: [],
    }));
}
