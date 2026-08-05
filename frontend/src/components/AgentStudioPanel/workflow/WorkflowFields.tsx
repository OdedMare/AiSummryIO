import { Save, Sparkles } from "lucide-react";
import type { WorkflowEditorController } from "./useWorkflowEditor";
import { WorkflowFieldAgent } from "./WorkflowAgents";

export function WorkflowFields({
  editor,
}: {
  editor: WorkflowEditorController;
}) {
  const { form, update } = editor;
  return (
    <>
      <div className="form-grid two">
        <label><span>שם התהליך *
          <WorkflowFieldAgent field="name" editor={editor} /></span>
          <input value={form.name} placeholder="לדוגמה: תמונת מצב פיננסית"
            onChange={(event) => update("name", event.target.value)} />
          <small className="field-hint">
            שם קצר וברור שיופיע ברשימת התהליכים ובתוצאות.
          </small>
        </label>
        <label><span>תפקיד
          <WorkflowFieldAgent field="role" editor={editor} /></span>
          <select value={form.role}
            onChange={(event) => update("role", event.target.value)}>
            <option value="baseline">בסיס — תמיד בריצה הראשונה</option>
            <option value="detail">פירוט — לשאלות המשך</option>
            <option value="both">שניהם</option>
          </select>
          <small className="field-hint">
            קובע אם התהליך ירוץ בסיכום הראשוני, בשאלות המשך או בשניהם.
          </small>
        </label>
      </div>
      <label><span>מתי להשתמש בתהליך
        <WorkflowFieldAgent field="description" editor={editor} /></span>
        <textarea value={form.description}
          placeholder="לדוגמה: כשצריך לסכם את המצב הפיננסי של המזהה"
          onChange={(event) => update("description", event.target.value)}
          rows={2} />
        <small className="field-hint">
          מסביר לסוכן מתי לבחור בתהליך הזה.
        </small>
      </label>
    </>
  );
}

export function AdvancedWorkflowFields({
  editor,
}: {
  editor: WorkflowEditorController;
}) {
  return (
    <details className="advanced-block">
      <summary><Sparkles size={16} /> הנחיה, חוזה פלט ודוגמאות</summary>
      <label><span>הנחיית סיכום לתהליך
        <WorkflowFieldAgent field="system_prompt" editor={editor} /></span>
        <textarea value={editor.form.system_prompt}
          placeholder="לדוגמה: סכמו את הממצאים, הדגישו חריגות וציינו פערי מידע"
          onChange={(event) => editor.update(
            "system_prompt", event.target.value,
          )}
          rows={5} />
        <small className="field-hint">
          מסביר למודל איך לקרוא את הפלט ולנסח ממנו את סעיף הסיכום.
        </small>
      </label>
      <label><span>חוזה פלט (JSON Schema)</span>
        <textarea dir="ltr" value={editor.form.output_schema}
          placeholder={'{\n  "type": "object",\n  "properties": {}\n}'}
          onChange={(event) => editor.update(
            "output_schema", event.target.value,
          )}
          rows={5} />
        <small className="field-hint">
          מגדיר אילו שדות נוספים יוחזרו מעבר לחוזה הסיכום המשותף.
        </small>
      </label>
      <label><span>דוגמאות משולבות ובדיקות (JSON)</span>
        <textarea dir="ltr" value={editor.form.examples}
          placeholder={'[\n  { "id": "001234567", "expected": "סיכום קצר" }\n]'}
          onChange={(event) => editor.update("examples", event.target.value)}
          rows={6} />
        <small className="field-hint">
          דוגמאות JSON שמשמשות לבדיקה ולאימות לפני פרסום.
        </small>
      </label>
    </details>
  );
}

export function WorkflowActions({
  editor,
}: {
  editor: WorkflowEditorController;
}) {
  return (
    <div className="form-actions">
      {editor.form.workflow_key
        && <button type="button" className="secondary-button"
          onClick={editor.reset}>ביטול עריכה</button>}
      <button className="primary-button" type="submit"
        disabled={editor.saving || !editor.steps.length}>
        <Save size={17} /> {editor.saving ? "שומר…" : "שמירת טיוטה"}
      </button>
    </div>
  );
}
