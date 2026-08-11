import type {
  Dispatch,
  DragEvent,
  SetStateAction,
} from "react";
import {
  Beaker,
  Eye,
  EyeOff,
  GripVertical,
  LoaderCircle,
} from "lucide-react";
import type { PackageInspection } from "@/types";
import {
  allowFieldDrop,
  FIELD_MIME,
  type FieldTarget,
  inspectionDisabled,
  type PackageForm,
  type SchemaField,
  schemaFields,
  setFieldPolicy,
  type UpdatePackage,
} from "./packageModel";

export function FieldPalette({
  form,
  update,
  target,
  setTarget,
  onInsert,
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
            onToggle={(listened) => update(
              "output_schema",
              setFieldPolicy(form.output_schema, field.name, listened),
            )} />)}
      </div>
    </section>
  );
}

function FieldChip({
  field,
  onInsert,
  onToggle,
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
        {field.listened
          ? <Eye size={16} aria-hidden="true" />
          : <EyeOff size={16} aria-hidden="true" />}
        <span>{field.listened ? "להקשיב" : "להתעלם"}</span>
      </label>
    </div>
  );
}

export function PackageInspector({
  form,
  inspectId,
  setInspectId,
  inspecting,
  inspect,
  inspection,
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
	        <p>מריץ מזהה אחד, כולל MULTIPOLYGON WKT, ומסיק output schema.</p>
      </div></header>
	      <label><span>מזהה / MULTIPOLYGON לבדיקה</span><input dir="ltr" value={inspectId}
        onChange={(event) => setInspectId(event.target.value)} /></label>
      <button type="button" className="secondary-button"
        onClick={() => void inspect()}
        disabled={inspectionDisabled(form, inspectId, inspecting)}>
        {inspecting
          ? <LoaderCircle className="spin" size={17} />
          : <Beaker size={17} />}
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

export function AdvancedPackageFields({
  form,
  update,
  onDropField,
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
        <textarea dir="ltr" value={form.output_schema}
          onDragOver={allowFieldDrop}
          onDrop={(event) => onDropField(event, "output_schema")}
          onChange={(event) => update("output_schema", event.target.value)}
          rows={7} />
      </label>
      <label><span>מזהי דוגמה (JSON)</span><textarea dir="ltr"
        value={form.example_input}
        onChange={(event) => update("example_input", event.target.value)}
        rows={3} />
      </label>
      <label className="field-drop-target"><span>פלט חבילה לדוגמה (JSON)
        <small>גרירת שדה מוסיפה אותו עם ערך מה־preview</small></span>
        <textarea dir="ltr" value={form.example_output}
          onDragOver={allowFieldDrop}
          onDrop={(event) => onDropField(event, "example_output")}
          onChange={(event) => update("example_output", event.target.value)}
          rows={6} />
      </label>
    </details>
  );
}
