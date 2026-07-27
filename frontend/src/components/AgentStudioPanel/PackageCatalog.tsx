"use client";

import {
  Dispatch, DragEvent, FormEvent, SetStateAction, useState,
} from "react";
import {
  ArrowLeft, Beaker, CheckCircle2, Eye, EyeOff, GripVertical, LoaderCircle,
  PackagePlus, Save, Wrench,
} from "lucide-react";
import { api } from "@/services/api";
import type { PackageInspection, PackageVersion } from "@/types";
import { emptyPackage, parseJson } from "./forms";

type PackageForm = typeof emptyPackage;
type FieldTarget =
  "description" | "agent_instructions" | "output_schema" | "example_output";
type SchemaField = {
  name: string;
  type: string;
  description: string;
  listened: boolean;
};
type UpdatePackage = <Key extends keyof PackageForm>(
  key: Key, value: PackageForm[Key]
) => void;
const FIELD_MIME = "application/x-aisummry-field";

export default function PackageCatalog({
  items, onRefresh,
}: {
  items: PackageVersion[];
  onRefresh: () => Promise<void>;
}) {
  const [form, setForm] = useState(emptyPackage);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [inspectId, setInspectId] = useState("");
  const [inspection, setInspection] = useState<PackageInspection | null>(null);
  const [inspecting, setInspecting] = useState(false);
  const [fieldTarget, setFieldTarget] =
    useState<FieldTarget>("agent_instructions");

  const update = <Key extends keyof typeof emptyPackage>(
    key: Key, value: (typeof emptyPackage)[Key],
  ) => setForm((current) => ({ ...current, [key]: value }));

  const edit = (item: PackageVersion) => {
    setForm({
      package_key: item.package_key, name: item.name,
      description: item.description, package_id: item.package_id,
      input_cube_name: item.input_cube_name,
      input_cube_parameter: item.input_cube_parameter,
      input_mode: item.input_mode, output_cube_name: item.output_cube_name,
      query_name: item.query_name, agent_enabled: item.agent_enabled,
      agent_instructions: item.agent_instructions,
      output_schema: JSON.stringify(item.output_schema || {}, null, 2),
      example_input: JSON.stringify(item.example_input, null, 2),
      example_output: JSON.stringify(item.example_output, null, 2),
    });
    setInspection(null); setMessage("");
  };

  const save = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError(""); setMessage("");
    try {
      await api.createPackage(packagePayload(form));
      setMessage("נשמרה גרסת טול חדשה.");
      setForm(emptyPackage); setInspection(null); await onRefresh();
    } catch (reason) {
      setError(errorMessage(reason, "השמירה נכשלה"));
    } finally {
      setSaving(false);
    }
  };

  const inspect = async () => {
    if (!inspectId.trim()) return setError("יש להזין מזהה בדיקה בטוח");
    setInspecting(true); setError(""); setMessage("");
    try {
      const result = await api.inspectPackage({
        ...packagePayload(form), root_id: inspectId.trim(),
      });
      setInspection(result);
      setForm((current) => ({
        ...current,
        description: current.description.trim()
          ? current.description : result.metadata_suggestions.description,
        agent_instructions: current.agent_instructions.trim()
          ? current.agent_instructions
          : result.metadata_suggestions.agent_instructions,
        output_schema: JSON.stringify(result.output_schema, null, 2),
        example_input: emptyJsonArray(current.example_input)
          ? JSON.stringify([inspectId.trim()], null, 2)
          : current.example_input,
        example_output: emptyJsonArray(current.example_output)
          ? JSON.stringify(result.records, null, 2)
          : current.example_output,
      }));
      setMessage(result.metadata_suggestions.description
        ? "השדות והצעות המטא־דאטה נטענו. אפשר לערוך, לגרור ולבחור למה להקשיב."
        : "השדות נטענו מההרצה. יצירת המטא־דאטה לא הייתה זמינה.");
    } catch (reason) {
      setInspection(null);
      setError(errorMessage(reason, "בדיקת הטול נכשלה"));
    } finally {
      setInspecting(false);
    }
  };

  return (
    <div className="studio-split">
      <PackageList items={items} onEdit={edit} />
      <form className="studio-form" onSubmit={save}>
        <FormHeader editing={!!form.package_key} />
        <PackageFields form={form} update={update}
          onDropField={(event, target) =>
            dropTextField(event, target, setForm)} />
        <Inspector form={form} inspectId={inspectId} setInspectId={setInspectId}
          inspecting={inspecting} inspect={inspect} inspection={inspection} />
        <FieldPalette form={form} update={update} target={fieldTarget}
          setTarget={setFieldTarget}
          onInsert={(field) => setForm((current) =>
            insertField(current, field, fieldTarget, inspection))} />
        <AdvancedFields form={form} update={update}
          onDropField={(event, target) =>
            dropJsonField(event, target, inspection, setForm)} />
        {error && <p className="form-error" role="alert">{error}</p>}
        {message && <p className="form-success">
          <CheckCircle2 size={16} /> {message}
        </p>}
        <div className="form-actions">
          {form.package_key && <button type="button" className="secondary-button"
            onClick={() => { setForm(emptyPackage); setInspection(null); }}>
            ביטול עריכה
          </button>}
          <button className="primary-button" type="submit" disabled={saving}>
            <Save size={17} /> {saving ? "שומר…" : "שמירת גרסה"}
          </button>
        </div>
      </form>
    </div>
  );
}

function PackageList({
  items, onEdit,
}: {
  items: PackageVersion[];
  onEdit: (item: PackageVersion) => void;
}) {
  return (
    <section className="studio-list">
      <header><h3>מקורות מידע</h3><span>{items.length} מקורות</span></header>
      {items.map((item) => (
        <button type="button" className="catalog-card" key={item.id}
          onClick={() => onEdit(item)}>
          <span className="catalog-icon"><Wrench size={18} /></span>
          <span><strong>{item.name}</strong><small>
            <bdi dir="ltr">{item.package_id} · v{item.version}</bdi>{" · "}
            {item.agent_enabled ? "זמין לסוכן" : "ל-workflow בלבד"}
          </small></span>
          <ArrowLeft size={16} />
        </button>
      ))}
      {!items.length &&
        <p className="panel-empty">הוסיפו את מקור המידע הראשון.</p>}
    </section>
  );
}

function FormHeader({ editing }: { editing: boolean }) {
  return (
    <header><span><PackagePlus size={19} /></span><div>
      <h3>{editing ? "גרסה חדשה למקור" : "מקור מידע חדש"}</h3>
      <p>חבילת FLAPI שמביאה נתונים לתהליך הסיכום.</p>
    </div></header>
  );
}

function PackageFields({
  form, update, onDropField,
}: {
  form: PackageForm;
  update: UpdatePackage;
  onDropField: (
    event: DragEvent<HTMLTextAreaElement>,
    target: "description" | "agent_instructions",
  ) => void;
}) {
  return (
    <>
      <div className="form-grid two">
        <label><span>שם תצוגה *</span><input value={form.name}
          onChange={(e) => update("name", e.target.value)} /></label>
        <label><span>Package ID *</span><input dir="ltr" value={form.package_id}
          onChange={(e) => update("package_id", e.target.value)} /></label>
        <label><span>Input cube *</span><input dir="ltr"
          value={form.input_cube_name}
          onChange={(e) => update("input_cube_name", e.target.value)} /></label>
        <label><span>Input parameter *</span><input dir="ltr"
          value={form.input_cube_parameter}
          onChange={(e) => update("input_cube_parameter", e.target.value)} />
        </label>
        <label><span>מצב קלט</span><select value={form.input_mode}
          onChange={(e) => update("input_mode", e.target.value)}>
          <option value="single">מזהה יחיד בכל הרצה</option>
          <option value="many">רשימת מזהים בהרצה אחת</option>
        </select></label>
        <label><span>Output cube *</span><input dir="ltr"
          value={form.output_cube_name}
          onChange={(e) => update("output_cube_name", e.target.value)} /></label>
      </div>
      <label className="field-drop-target"><span>מתי הטול שימושי
        <small>אפשר לגרור לכאן שדות</small></span>
        <textarea value={form.description}
          onDragOver={allowFieldDrop}
          onDrop={(event) => onDropField(event, "description")}
          onChange={(e) => update("description", e.target.value)} rows={2} />
      </label>
      <label className="field-drop-target">
        <span>איך לסכם את תוצאות הטול
          <small>אפשר לגרור לכאן שדות</small></span>
        <textarea value={form.agent_instructions}
          onDragOver={allowFieldDrop}
          onDrop={(event) => onDropField(event, "agent_instructions")}
          onChange={(e) => update("agent_instructions", e.target.value)}
          rows={3} />
      </label>
      <label className="agent-tool-toggle">
        <input type="checkbox" checked={form.agent_enabled}
          onChange={(e) => update("agent_enabled", e.target.checked)} />
        <span>זמין לסוכן כטול עצמאי
          <small>מאפשר לבחור בטול לשאלת העמקה גם בלי workflow מוכן.</small>
        </span>
      </label>
      <label><span>Query name (לא חובה)</span><input dir="ltr"
        value={form.query_name}
        onChange={(e) => update("query_name", e.target.value)} /></label>
    </>
  );
}

function FieldPalette({
  form, update, target, setTarget, onInsert,
}: {
  form: PackageForm;
  update: UpdatePackage;
  target: FieldTarget;
  setTarget: Dispatch<SetStateAction<FieldTarget>>;
  onInsert: (field: string) => void;
}) {
  const fields = schemaFields(form.output_schema);
  if (!fields.length) return null;
  return (
    <section className="field-palette" aria-labelledby="field-palette-title">
      <header>
        <div><h4 id="field-palette-title">שדות הטול</h4>
          <p>גררו שדה ליעד, או בחרו יעד ולחצו על השדה.</p></div>
        <label><span>יעד ללחיצה</span>
          <select value={target}
            onChange={(event) => setTarget(event.target.value as FieldTarget)}>
            <option value="agent_instructions">הנחיות סיכום</option>
            <option value="description">תיאור הטול</option>
            <option value="output_schema">Output schema JSON</option>
            <option value="example_output">פלט לדוגמה JSON</option>
          </select>
        </label>
      </header>
      <div className="field-chip-list">
        {fields.map((field) =>
          <FieldChip key={field.name} field={field}
            onInsert={() => onInsert(field.name)}
            onToggle={(listened) =>
              update("output_schema", setFieldPolicy(
                form.output_schema, field.name, listened
              ))} />
        )}
      </div>
    </section>
  );
}

function FieldChip({
  field, onInsert, onToggle,
}: {
  field: SchemaField;
  onInsert: () => void;
  onToggle: (listened: boolean) => void;
}) {
  return (
    <div className={`field-chip ${field.listened ? "listening" : "ignored"}`}>
      <button type="button" draggable onClick={onInsert}
        onDragStart={(event) => {
          event.dataTransfer.setData(FIELD_MIME, field.name);
          event.dataTransfer.setData("text/plain", field.name);
          event.dataTransfer.effectAllowed = "copy";
        }}
        aria-label={`הוספת השדה ${field.name} ליעד שנבחר`}>
        <GripVertical size={17} aria-hidden="true" />
        <span><bdi dir="ltr">{field.name}</bdi>
          <small>{field.description || field.type}</small></span>
      </button>
      <label>
        <input type="checkbox" checked={field.listened}
          onChange={(event) => onToggle(event.target.checked)} />
        {field.listened ? <Eye size={16} /> : <EyeOff size={16} />}
        <span>{field.listened ? "להקשיב" : "להתעלם"}</span>
      </label>
    </div>
  );
}

function Inspector({
  form, inspectId, setInspectId, inspecting, inspect, inspection,
}: {
  form: PackageForm;
  inspectId: string;
  setInspectId: Dispatch<SetStateAction<string>>;
  inspecting: boolean;
  inspect: () => Promise<void>;
  inspection: PackageInspection | null;
}) {
  return (
    <section className="tool-inspector" aria-labelledby="tool-inspector-title">
      <header><div><h4 id="tool-inspector-title">Fetch 1 ID</h4>
        <p>מריץ מזהה אחד, מציג preview מוגבל ומסיק את ה-output schema.</p>
      </div></header>
      <label><span>מזהה בדיקה בטוח</span><input dir="ltr" value={inspectId}
        onChange={(e) => setInspectId(e.target.value)} /></label>
      <button type="button" className="secondary-button"
        onClick={() => void inspect()} disabled={inspectionDisabled(
          form, inspectId, inspecting
        )}>
        {inspecting ? <LoaderCircle className="spin" size={17} /> :
          <Beaker size={17} />}
        {inspecting ? "מביא פלט…" : "Fetch 1 ID"}
      </button>
      {inspection && <div className="inspection-result" aria-live="polite">
        <strong>התקבלו {inspection.row_count} רשומות
          {inspection.truncated ? " · מוצגות 20 ראשונות" : ""}
        </strong>
        <pre dir="ltr">{JSON.stringify(inspection.records, null, 2)}</pre>
      </div>}
    </section>
  );
}

function AdvancedFields({
  form, update, onDropField,
}: {
  form: PackageForm;
  update: UpdatePackage;
  onDropField: (
    event: DragEvent<HTMLTextAreaElement>,
    target: "output_schema" | "example_output",
  ) => void;
}) {
  return (
    <details className="advanced-block">
      <summary><Beaker size={16} /> Schema ודוגמאות קלט ופלט</summary>
      <label className="field-drop-target"><span>Output schema
        <small>גרירת שדה לכאן מסמנת אותו לשימוש בסיכום</small></span>
        <textarea dir="ltr"
        value={form.output_schema}
        onDragOver={allowFieldDrop}
        onDrop={(event) => onDropField(event, "output_schema")}
        onChange={(e) => update("output_schema", e.target.value)} rows={7} />
      </label>
      <label><span>מזהי דוגמה (JSON)</span><textarea dir="ltr"
        value={form.example_input}
        onChange={(e) => update("example_input", e.target.value)} rows={3} />
      </label>
      <label className="field-drop-target"><span>פלט חבילה לדוגמה (JSON)
        <small>גרירת שדה מוסיפה אותו עם ערך מה־preview</small></span>
        <textarea dir="ltr"
        value={form.example_output}
        onDragOver={allowFieldDrop}
        onDrop={(event) => onDropField(event, "example_output")}
        onChange={(e) => update("example_output", e.target.value)} rows={6} />
      </label>
    </details>
  );
}

function packagePayload(form: typeof emptyPackage) {
  return {
    ...form, package_key: form.package_key || undefined,
    output_schema: parseJson<Record<string, unknown>>(form.output_schema, {}),
    example_input: parseJson<string[]>(form.example_input, []),
    example_output: parseJson<Array<Record<string, unknown>>>(
      form.example_output, []
    ),
  };
}

function inspectionDisabled(
  form: PackageForm, inspectId: string, inspecting: boolean
) {
  return inspecting || !inspectId.trim() || !form.name.trim() ||
    !form.package_id.trim() || !form.input_cube_name.trim() ||
    !form.input_cube_parameter.trim() || !form.output_cube_name.trim();
}

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}

function schemaFields(value: string): SchemaField[] {
  try {
    const schema = JSON.parse(value) as {
      properties?: Record<string, unknown>;
    };
    return Object.entries(schema.properties ?? {}).map(([name, raw]) => {
      const definition = (
        raw && typeof raw === "object" ? raw : {}
      ) as Record<string, unknown>;
      const type = Array.isArray(definition.type)
        ? definition.type.join(" / ") : String(definition.type ?? "unknown");
      return {
        name, type,
        description: typeof definition.description === "string"
          ? definition.description : "",
        listened: definition["x-summary"] !== false,
      };
    });
  } catch {
    return [];
  }
}

function setFieldPolicy(value: string, field: string, listened: boolean) {
  const schema = parseJson<Record<string, unknown>>(value, {});
  const properties = (
    schema.properties && typeof schema.properties === "object"
      ? schema.properties : {}
  ) as Record<string, unknown>;
  const current = properties[field];
  properties[field] = {
    ...(current && typeof current === "object" ? current : {}),
    "x-summary": listened,
  };
  return JSON.stringify({ ...schema, properties }, null, 2);
}

function allowFieldDrop(event: DragEvent<HTMLTextAreaElement>) {
  if (event.dataTransfer.types.includes(FIELD_MIME)) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }
}

function draggedField(event: DragEvent<HTMLTextAreaElement>) {
  return event.dataTransfer.getData(FIELD_MIME);
}

function dropTextField(
  event: DragEvent<HTMLTextAreaElement>,
  target: "description" | "agent_instructions",
  setForm: Dispatch<SetStateAction<PackageForm>>,
) {
  const field = draggedField(event);
  if (!field) return;
  event.preventDefault();
  const start = event.currentTarget.selectionStart;
  const end = event.currentTarget.selectionEnd;
  setForm((current) => ({
    ...current,
    [target]: insertText(current[target], `\`${field}\``, start, end),
  }));
}

function dropJsonField(
  event: DragEvent<HTMLTextAreaElement>,
  target: "output_schema" | "example_output",
  inspection: PackageInspection | null,
  setForm: Dispatch<SetStateAction<PackageForm>>,
) {
  const field = draggedField(event);
  if (!field) return;
  event.preventDefault();
  setForm((current) => insertField(current, field, target, inspection));
}

function insertField(
  form: PackageForm,
  field: string,
  target: FieldTarget,
  inspection: PackageInspection | null,
): PackageForm {
  if (target === "description" || target === "agent_instructions") {
    return { ...form, [target]: appendText(form[target], `\`${field}\``) };
  }
  if (target === "output_schema") {
    return {
      ...form,
      output_schema: setFieldPolicy(form.output_schema, field, true),
    };
  }
  const rows = parseJson<Array<Record<string, unknown>>>(
    form.example_output, []
  );
  const sample = inspection?.records[0]?.[field] ?? null;
  const [first = {}, ...rest] = rows;
  return {
    ...form,
    example_output: JSON.stringify([
      { ...first, [field]: sample }, ...rest,
    ], null, 2),
  };
}

function appendText(value: string, token: string) {
  return value.trimEnd() + (value.trim() ? " " : "") + token;
}

function insertText(
  value: string, token: string, start: number, end: number,
) {
  const before = value.slice(0, start);
  const after = value.slice(end);
  const leading = before && !/\s$/.test(before) ? " " : "";
  const trailing = after && !/^\s/.test(after) ? " " : "";
  return before + leading + token + trailing + after;
}

function emptyJsonArray(value: string) {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) && parsed.length === 0;
  } catch {
    return false;
  }
}
