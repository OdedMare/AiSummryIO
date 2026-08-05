import type { DragEvent } from "react";
import { ArrowLeft, PackagePlus, Trash2, Wrench } from "lucide-react";
import type {
  PackageInspection,
  PackageVersion,
  ToolPlanDraft,
} from "@/types";
import { PackageFieldAgent, ToolPlanChat } from "./PackageAgents";
import {
  allowFieldDrop,
  type PackageForm,
  type UpdatePackage,
} from "./packageModel";

export function PackageList({
  items,
  onEdit,
  onRemove,
}: {
  items: PackageVersion[];
  onEdit: (item: PackageVersion) => void;
  onRemove: (item: PackageVersion) => void;
}) {
  return (
    <section className="studio-list">
      <header><h3>מקורות מידע</h3><span>{items.length} מקורות</span></header>
      {items.map((item) =>
        <article className="catalog-card" key={item.id}>
          <button type="button" className="catalog-card-main"
            onClick={() => onEdit(item)}>
            <span className="catalog-icon"><Wrench size={18} /></span>
            <span><strong>{item.name}</strong><small>
              <bdi dir="ltr">{item.package_id} · v{item.version}</bdi>{" · "}
              {item.agent_enabled ? "זמין לסוכן" : "ל-workflow בלבד"}
            </small></span>
            <ArrowLeft size={16} />
          </button>
          <button type="button" className="catalog-card-delete"
            onClick={() => onRemove(item)}
            aria-label={`מחיקת הטול ${item.name}`} title="מחיקת הטול">
            <Trash2 size={15} aria-hidden="true" />
          </button>
        </article>)}
      {!items.length
        && <p className="panel-empty">הוסיפו את מקור המידע הראשון.</p>}
    </section>
  );
}

export function PackageFormHeader({
  form,
  editing,
  inspection,
  onApply,
}: {
  form: PackageForm;
  editing: boolean;
  inspection: PackageInspection | null;
  onApply: (draft: ToolPlanDraft) => void;
}) {
  return (
    <header className="studio-form-header">
      <span><PackagePlus size={19} /></span>
      <div>
        <h3>{editing ? "גרסה חדשה למקור" : "מקור מידע חדש"}</h3>
        <p>חבילת FLAPI שמביאה נתונים לתהליך הסיכום.</p>
      </div>
      <ToolPlanChat form={form} inspection={inspection} onApply={onApply} />
    </header>
  );
}

export function PackageFields({
  form,
  update,
  onDropField,
  inspection,
  onApplyField,
}: {
  form: PackageForm;
  update: UpdatePackage;
  onDropField: (
    event: DragEvent<HTMLTextAreaElement>,
    target: "description" | "agent_instructions",
  ) => void;
  inspection: PackageInspection | null;
  onApplyField: (field: keyof ToolPlanDraft, value: string) => void;
}) {
  const agent = (field: keyof ToolPlanDraft) => (
    <PackageFieldAgent field={field} form={form} inspection={inspection}
      onApply={onApplyField} />
  );
  return (
    <>
      <div className="form-grid two">
        <label><span>שם תצוגה *{agent("name")}</span>
          <input value={form.name}
            onChange={(event) => update("name", event.target.value)} />
        </label>
        <label><span>Package ID *</span><input dir="ltr" value={form.package_id}
          onChange={(event) => update("package_id", event.target.value)} />
        </label>
        <label><span>Input cube *</span><input dir="ltr"
          value={form.input_cube_name}
          onChange={(event) => update("input_cube_name", event.target.value)} />
        </label>
        <label><span>Input parameter *</span><input dir="ltr"
          value={form.input_cube_parameter}
          onChange={(event) => update(
            "input_cube_parameter", event.target.value,
          )} />
        </label>
        <label><span>מצב קלט</span><select value={form.input_mode}
          onChange={(event) => update("input_mode", event.target.value)}>
          <option value="single">מזהה יחיד בכל הרצה</option>
          <option value="many">רשימת מזהים בהרצה אחת</option>
        </select></label>
        <label><span>Output cube *</span><input dir="ltr"
          value={form.output_cube_name}
          onChange={(event) => update("output_cube_name", event.target.value)} />
        </label>
      </div>
      <label className="field-drop-target"><span>מתי הטול שימושי
        <small>אפשר לגרור לכאן שדות</small>{agent("description")}</span>
        <textarea value={form.description} onDragOver={allowFieldDrop}
          onDrop={(event) => onDropField(event, "description")}
          onChange={(event) => update("description", event.target.value)}
          rows={2} />
      </label>
      <label className="field-drop-target">
        <span>איך לסכם את תוצאות הטול
          <small>אפשר לגרור לכאן שדות</small>
          {agent("agent_instructions")}</span>
        <textarea value={form.agent_instructions} onDragOver={allowFieldDrop}
          onDrop={(event) => onDropField(event, "agent_instructions")}
          onChange={(event) => update(
            "agent_instructions", event.target.value,
          )}
          rows={3} />
      </label>
      <label className="agent-tool-toggle">
        <input type="checkbox" checked={form.agent_enabled}
          onChange={(event) => update("agent_enabled", event.target.checked)} />
        <span>זמין לסוכן כטול עצמאי
          <small>מאפשר לבחור בטול לשאלת העמקה גם בלי workflow מוכן.</small>
        </span>
      </label>
      <label><span>Query name (לא חובה)</span><input dir="ltr"
        value={form.query_name}
        onChange={(event) => update("query_name", event.target.value)} />
      </label>
    </>
  );
}
