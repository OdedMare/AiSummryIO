import { useState } from "react";
import { api } from "@/services/api";
import type { PackageInspection, ToolPlanDraft } from "@/types";
import {
  FieldAgentPopover,
  PlanChat,
  PlanChatDrawer,
  usePlanChat,
} from "../PlanChat";
import {
  connectionDraft,
  fieldPreview,
  type PackageForm,
} from "./packageModel";

const AUTHORED_LABELS: Array<[
  keyof ToolPlanDraft,
  string,
  "rtl" | "ltr",
]> = [
  ["name", "שם תצוגה", "rtl"],
  ["description", "מתי הטול שימושי", "rtl"],
  ["agent_instructions", "איך לסכם", "rtl"],
  ["output_schema", "Output schema", "ltr"],
  ["example_input", "קלט לדוגמה", "ltr"],
  ["example_output", "פלט לדוגמה", "ltr"],
];

export function ToolPlanChat({
  form,
  inspection,
  onApply,
}: {
  form: PackageForm;
  inspection: PackageInspection | null;
  onApply: (draft: ToolPlanDraft) => void;
}) {
  const [open, setOpen] = useState(false);
  const chat = usePlanChat<ToolPlanDraft>(
    (messages, draft) => api.planToolChat(
      messages,
      { ...connectionDraft(form), ...(draft ?? {}) },
      inspection,
    ),
    (readyDraft) => {
      onApply(readyDraft);
      setOpen(false);
    },
  );
  const draft = chat.draft;
  const filled = draft
    ? AUTHORED_LABELS.filter(([field]) => draft[field]).length
    : 0;
  return (
    <PlanChatDrawer open={open} busy={chat.pending}
      onOpen={() => setOpen(true)} onClose={() => setOpen(false)}
      label="שאלו את הסוכן" disabled={!inspection}
      disabledHint="הריצו Fetch 1 ID כדי שהסוכן יראה את הנתונים האמיתיים">
      <PlanChat chat={chat} title="תשאול על הטול"
        hint="הסוכן ראה את הפלט של ההרצה. הוא ישאל שאלה אחת בכל פעם, עם המלצה, ויציע את הניסוח שהמודל יקרא בזמן הסיכום.">
        {draft && <div className="planner-result" aria-live="polite">
          <p className="plan-chat-count">
            נוסחו {filled} מתוך {AUTHORED_LABELS.length} שדות
          </p>
          <dl className="plan-chat-draft">
            {AUTHORED_LABELS.map(([field, label, dir]) =>
              <div key={field} className={draft[field] ? "filled" : "empty"}>
                <dt>{label}</dt>
                <dd dir={dir}>{fieldPreview(draft[field])}</dd>
              </div>)}
            <div className={draft.agent_enabled ? "filled" : "empty"}>
              <dt>זמין לסוכן</dt>
              <dd>{draft.agent_enabled ? "כן" : "ל-workflow בלבד"}</dd>
            </div>
          </dl>
        </div>}
      </PlanChat>
    </PlanChatDrawer>
  );
}

const FIELD_AGENT_LABELS: Partial<Record<keyof ToolPlanDraft, string>> = {
  name: "שם תצוגה",
  description: "מתי הטול שימושי",
  agent_instructions: "איך לסכם את תוצאות הטול",
  output_schema: "Output schema",
  example_input: "קלט לדוגמה",
  example_output: "פלט לדוגמה",
};

export function PackageFieldAgent({
  field,
  form,
  inspection,
  onApply,
}: {
  field: keyof ToolPlanDraft;
  form: PackageForm;
  inspection: PackageInspection | null;
  onApply: (field: keyof ToolPlanDraft, value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const label = FIELD_AGENT_LABELS[field] ?? field;
  const chat = usePlanChat<ToolPlanDraft>(
    (messages, draft) => api.planToolChat(
      messages,
      { ...connectionDraft(form), ...(draft ?? {}) },
      inspection,
      field,
    ),
    (readyDraft) => {
      const offered = readyDraft[field];
      if (typeof offered === "string" && offered) onApply(field, offered);
      setOpen(false);
    },
  );
  const offered = chat.draft?.[field];
  const value = typeof offered === "string" ? offered : "";
  const direction = field === "name" || field === "description"
    || field === "agent_instructions" ? "rtl" : "ltr";
  return (
    <FieldAgentPopover open={open} field={field} label={label}
      busy={chat.pending}
      onOpen={() => setOpen(true)} onClose={() => setOpen(false)}
      disabled={!inspection} disabledHint="הריצו Fetch 1 ID קודם">
      <PlanChat chat={chat} title={label}
        hint={`הסוכן ראה את הפלט של ההרצה. שוחחו איתו על "${label}" בלבד.`}>
        {value && <div className="planner-result" aria-live="polite">
          <p className="field-agent-proposal-label">ההצעה לשדה:</p>
          <p className="field-agent-proposal" dir={direction}>{value}</p>
        </div>}
      </PlanChat>
    </FieldAgentPopover>
  );
}
