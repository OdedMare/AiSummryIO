"use client";

import { Dispatch, FormEvent, SetStateAction, useState } from "react";
import {
  ArrowLeft, Beaker, CheckCircle2, LoaderCircle, PackagePlus, Save, Wrench,
} from "lucide-react";
import { api } from "@/services/api";
import type { PackageInspection, PackageVersion } from "@/types";
import { emptyPackage, parseJson } from "./forms";

type PackageForm = typeof emptyPackage;
type UpdatePackage = <Key extends keyof PackageForm>(
  key: Key, value: PackageForm[Key]
) => void;

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
      setForm((current) => ({ ...current,
        output_schema: JSON.stringify(result.output_schema, null, 2) }));
      setMessage("ה-schema הוסק מההרצה ונטען לטופס. יש לבדוק לפני שמירה.");
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
        <PackageFields form={form} update={update} />
        <Inspector form={form} inspectId={inspectId} setInspectId={setInspectId}
          inspecting={inspecting} inspect={inspect} inspection={inspection} />
        <AdvancedFields form={form} update={update} />
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
  form, update,
}: {
  form: PackageForm;
  update: UpdatePackage;
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
      <label><span>מתי הטול שימושי</span><textarea value={form.description}
        onChange={(e) => update("description", e.target.value)} rows={2} />
      </label>
      <label><span>איך לסכם את תוצאות הטול</span>
        <textarea value={form.agent_instructions}
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
  form, update,
}: {
  form: PackageForm;
  update: UpdatePackage;
}) {
  return (
    <details className="advanced-block">
      <summary><Beaker size={16} /> Schema ודוגמאות קלט ופלט</summary>
      <label><span>Output schema</span><textarea dir="ltr"
        value={form.output_schema}
        onChange={(e) => update("output_schema", e.target.value)} rows={7} />
      </label>
      <label><span>מזהי דוגמה (JSON)</span><textarea dir="ltr"
        value={form.example_input}
        onChange={(e) => update("example_input", e.target.value)} rows={3} />
      </label>
      <label><span>פלט חבילה לדוגמה (JSON)</span><textarea dir="ltr"
        value={form.example_output}
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
