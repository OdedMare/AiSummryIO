import { FormEvent, useState } from "react";
import { api } from "@/services/api";
import type {
  PackageInspection,
  PackageVersion,
  ToolPlanDraft,
} from "@/types";
import { emptyPackage } from "../forms";
import {
  emptyJsonArray,
  errorMessage,
  type FieldTarget,
  insertField,
  packageForm,
  packagePayload,
} from "./packageModel";

export function usePackageCatalog(
  onRefresh: () => Promise<void>,
) {
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
    key: Key,
    value: (typeof emptyPackage)[Key],
  ) => setForm((current) => ({ ...current, [key]: value }));

  const edit = (item: PackageVersion) => {
    setForm(packageForm(item));
    setInspection(null);
    setMessage("");
  };

  const applyDraft = (draft: ToolPlanDraft) => {
    setForm((current) => ({
      ...current,
      name: draft.name || current.name,
      description: draft.description || current.description,
      agent_instructions: draft.agent_instructions || current.agent_instructions,
      agent_enabled: draft.agent_enabled,
      output_schema: draft.output_schema || current.output_schema,
      example_input: draft.example_input || current.example_input,
      example_output: draft.example_output || current.example_output,
    }));
    setMessage("הצעת הסוכן נטענה לטופס. יש לערוך ולאשר לפני השמירה.");
  };

  const applyField = (field: keyof ToolPlanDraft, value: string) => {
    if (!(field in emptyPackage) || !value) return;
    setForm((current) => ({ ...current, [field]: value }));
    setMessage("הצעת הסוכן נטענה לשדה. יש לבדוק אותה לפני השמירה.");
  };

  const reset = () => {
    setForm(emptyPackage);
    setInspection(null);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await api.createPackage(packagePayload(form));
      setMessage("נשמרה גרסת טול חדשה.");
      reset();
      await onRefresh();
    } catch (reason) {
      setError(errorMessage(reason, "השמירה נכשלה"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item: PackageVersion) => {
    const confirmed = window.confirm(
      `למחוק את הטול „${item.name}” על כל הגרסאות שלו? הפעולה אינה הפיכה.`,
    );
    if (!confirmed) return;
    setError("");
    setMessage("");
    try {
      await api.deletePackage(item.id);
      if (form.package_key === item.package_key) reset();
      setMessage(`הטול „${item.name}” נמחק.`);
      await onRefresh();
    } catch (reason) {
      setError(errorMessage(reason, "המחיקה נכשלה"));
    }
  };

  const inspect = async () => {
    if (!inspectId.trim()) {
      setError("יש להזין מזהה בדיקה בטוח");
      return;
    }
    setInspecting(true);
    setError("");
    setMessage("");
    try {
      const result = await api.inspectPackage({
        ...packagePayload(form),
        root_id: inspectId.trim(),
      });
      setInspection(result);
      setForm((current) => ({
        ...current,
        description: current.description.trim()
          ? current.description
          : result.metadata_suggestions.description,
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

  const insert = (field: string) => setForm((current) =>
    insertField(current, field, fieldTarget, inspection));

  return {
    form,
    setForm,
    error,
    message,
    saving,
    inspectId,
    setInspectId,
    inspection,
    inspecting,
    fieldTarget,
    setFieldTarget,
    update,
    edit,
    applyDraft,
    applyField,
    reset,
    save,
    remove,
    inspect,
    insert,
  };
}

export type PackageCatalogController = ReturnType<typeof usePackageCatalog>;
