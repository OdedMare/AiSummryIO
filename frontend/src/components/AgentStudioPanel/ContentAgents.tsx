import { useState } from "react";
import { api } from "@/services/api";
import type { SkillPlanDraft, SpecialistPlanDraft } from "@/types";
import { PlanChat, PlanChatDrawer, usePlanChat } from "./PlanChat";

export function SkillPlanChat({
  form,
  onApply,
}: {
  form: SkillPlanDraft;
  onApply: (draft: SkillPlanDraft) => void;
}) {
  const [open, setOpen] = useState(false);
  const chat = usePlanChat<SkillPlanDraft>(
    (messages, draft) => api.planSkillChat(
      messages, { ...form, ...(draft ?? {}) },
    ),
    (readyDraft) => {
      onApply(readyDraft);
      setOpen(false);
    },
  );
  return (
    <PlanChatDrawer open={open} busy={chat.pending}
      onOpen={() => setOpen(true)} onClose={() => setOpen(false)}
      label="שאלו את הסוכן">
      <PlanChat chat={chat} title="תשאול על ה־Skill"
        hint="ספרו איזה ניתוח המשתמש צריך לקבל. הסוכן ישאל שאלה אחת בכל פעם, ינסח הוראות מלאות, ולאחר אישור ימלא את הטופס.">
        {chat.draft && <SkillDraftPreview draft={chat.draft} />}
      </PlanChat>
    </PlanChatDrawer>
  );
}

export function SpecialistPlanChat({
  form,
  onApply,
}: {
  form: SpecialistPlanDraft & { content_key?: string };
  onApply: (draft: SpecialistPlanDraft) => void;
}) {
  const [open, setOpen] = useState(false);
  const chat = usePlanChat<SpecialistPlanDraft>(
    (messages, draft) => api.planSpecialistChat(
      messages, { ...form, ...(draft ?? {}) },
    ),
    (readyDraft) => {
      onApply(readyDraft);
      setOpen(false);
    },
  );
  return (
    <PlanChatDrawer open={open} busy={chat.pending}
      onOpen={() => setOpen(true)} onClose={() => setOpen(false)}
      label="שאלו את הסוכן">
      <PlanChat chat={chat} title="תשאול על המומחה"
        hint="ספרו על תחום האחריות. הסוכן יבחר רק Workflows ו־Skills קיימים, ינסח את ההנחיות, ולאחר אישור ימלא את הטופס.">
        {chat.draft && <SpecialistDraftPreview draft={chat.draft} />}
      </PlanChat>
    </PlanChatDrawer>
  );
}

function SkillDraftPreview({ draft }: { draft: SkillPlanDraft }) {
  return (
    <div className="planner-result" aria-live="polite">
      <dl className="plan-chat-draft">
        <DraftField label="שם" value={draft.name} />
        <DraftField label="תיאור" value={draft.description} />
        <DraftField label="הוראות" value={draft.content} direction="ltr" />
        <DraftField label="מוצג למשתמשים"
          value={draft.user_selectable ? "כן" : "לא"} />
        <DraftField label="פעיל לסוכן"
          value={draft.agent_enabled ? "כן" : "לא"} />
      </dl>
    </div>
  );
}

function SpecialistDraftPreview({ draft }: { draft: SpecialistPlanDraft }) {
  return (
    <div className="planner-result" aria-live="polite">
      <dl className="plan-chat-draft">
        <DraftField label="שם" value={draft.name} />
        <DraftField label="תחום אחריות" value={draft.description} />
        <DraftField label="הנחיות" value={draft.content} direction="ltr" />
        <DraftField label="Workflows"
          value={draft.workflow_keys.join(", ")} direction="ltr" />
        <DraftField label="Skills"
          value={draft.skill_keys.join(", ") || "ללא"} direction="ltr" />
        <DraftField label="פעיל לסוכן"
          value={draft.agent_enabled ? "כן" : "לא"} />
      </dl>
    </div>
  );
}

function DraftField({
  label,
  value,
  direction = "rtl",
}: {
  label: string;
  value: string;
  direction?: "rtl" | "ltr";
}) {
  return (
    <div className={value ? "filled" : "empty"}>
      <dt>{label}</dt>
      <dd dir={direction}>{preview(value)}</dd>
    </div>
  );
}

const preview = (value: string) => value.length > 220
  ? `${value.slice(0, 220)}…`
  : value || "טרם נוסח";
