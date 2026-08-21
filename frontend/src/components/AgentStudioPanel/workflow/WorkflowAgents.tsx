import { useState } from "react";
import { api } from "@/services/api";
import type { WorkflowPlan } from "@/types";
import {
  FieldAgentPopover,
  PlanChat,
  PlanChatDrawer,
  usePlanChat,
} from "../PlanChat";
import type { WorkflowEditorController } from "./useWorkflowEditor";

export function WorkflowPlanChat({
  editor,
}: {
  editor: WorkflowEditorController;
}) {
  const [open, setOpen] = useState(false);
  const chat = usePlanChat<WorkflowPlan>(
    (messages, draft) => api.planWorkflowChat(
      messages, draft, editor.projectId,
    ),
    (readyPlan) => {
      editor.loadPlan(readyPlan);
      setOpen(false);
    },
  );
  const plan = chat.draft;
  return (
    <PlanChatDrawer open={open} busy={chat.pending}
      onOpen={() => setOpen(true)} onClose={() => setOpen(false)}
      label="שאלו את הסוכן">
      <PlanChat chat={chat} title="תשאול על התהליך"
        hint="ספרו מה אתם רוצים לדעת על המזהה. הסוכן ישאל שאלה אחת בכל פעם, עם המלצה, עד שנגיע להסכמה.">
        {plan && <PlanPreview plan={plan} />}
      </PlanChat>
    </PlanChatDrawer>
  );
}

type WorkflowFocus =
  "name" | "role" | "description" | "system_prompt" | "steps";

const WORKFLOW_FIELD_LABELS: Record<WorkflowFocus, string> = {
  name: "שם התהליך",
  role: "תפקיד",
  description: "מתי להשתמש בתהליך",
  system_prompt: "הנחיית סיכום לתהליך",
  steps: "מה המסלול עושה",
};

export function WorkflowFieldAgent({
  field,
  editor,
}: {
  field: WorkflowFocus;
  editor: WorkflowEditorController;
}) {
  const [open, setOpen] = useState(false);
  const label = WORKFLOW_FIELD_LABELS[field];
  const chat = usePlanChat<WorkflowPlan>(
    (messages, draft) => api.planWorkflowChat(
      messages, draft, editor.projectId, field,
    ),
    (readyPlan) => {
      if (field === "steps") editor.loadPlanSteps(readyPlan);
      else {
        const offered = readyPlan[field];
        if (typeof offered === "string" && offered) {
          editor.update(field, offered);
        }
      }
      setOpen(false);
    },
  );
  const plan = chat.draft;
  const offerSteps = field === "steps" && !!plan?.steps.length
    && plan.can_build;
  const value = field === "steps" ? "" : (plan?.[field] ?? "");
  return (
    <FieldAgentPopover open={open} field={field} label={label}
      busy={chat.pending}
      onOpen={() => setOpen(true)} onClose={() => setOpen(false)}>
      <PlanChat chat={chat} title={label}
        hint={field === "steps"
          ? "ספרו מה המסלול צריך לענות עליו. הסוכן יציע שלבים מהקטלוג ואת החיבור ביניהם."
          : `שוחחו עם הסוכן על "${label}" בלבד.`}>
        {plan && <div className="planner-result" aria-live="polite">
          {field === "steps" && plan.rationale && <p>{plan.rationale}</p>}
          {offerSteps && <PlanSteps plan={plan} />}
          {field === "steps" && <MissingTools plan={plan} />}
          {value && <>
            <p className="field-agent-proposal-label">ההצעה לשדה:</p>
            <p className="field-agent-proposal">{value}</p>
          </>}
        </div>}
      </PlanChat>
    </FieldAgentPopover>
  );
}

function PlanPreview({ plan }: { plan: WorkflowPlan }) {
  return (
    <div className="planner-result" aria-live="polite">
      {plan.rationale && <p>{plan.rationale}</p>}
      {!!plan.steps.length && <PlanSteps plan={plan} />}
      <MissingTools plan={plan} />
    </div>
  );
}

function PlanSteps({ plan }: { plan: WorkflowPlan }) {
  return (
    <ol className="plan-chat-steps">
      {plan.steps.map((step) =>
        <li key={step.key}>
          <b dir="ltr">{step.key}</b> <span>{step.name}</span>
          <small dir="ltr">
            {step.input_source}
            {step.input_field ? ` → ${step.input_field}` : ""}
          </small>
        </li>)}
    </ol>
  );
}

function MissingTools({ plan }: { plan: WorkflowPlan }) {
  if (!plan.missing_tools.length) return null;
  return (
    <section>
      <strong>מה חסר כדי להשלים את הבקשה</strong>
      <ul>{plan.missing_tools.map((item, index) =>
        <li key={`${item.name}-${index}`}><b>{item.name}</b>
          <span>{item.reason}</span>
        </li>)}
      </ul>
    </section>
  );
}
