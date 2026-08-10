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
  /* Which catalog row this form is editing, or "" for a new tool. A tool is
     one row, edited in place, so saving an edit updates that row instead of
     appending a version beside it. */
  const [editingId, setEditingId] = useState("");
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
    setEditingId(item.id);
    setInspection(null);
    setMessage("");
    setError("");
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
    setEditingId("");
    setInspection(null);
  };
  /* Leaving an edit for a blank form. `reset` alone is what `save` calls
     after creating, where the success message has to survive. */
  const startNew = () => { reset(); setError(""); setMessage(""); };

  /** Update the tool being edited, or create a new one. */
  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const payload = packagePayload(form);
      if (editingId) {
        await api.updatePackage(editingId, payload);
        setMessage("הטול עודכן.");
      } else {
        await api.createPackage(payload);
        setMessage("נשמר טול חדש.");
        reset();
      }
      await onRefresh();
    } catch (reason) {
      setError(errorMessage(reason, "השמירה נכשלה"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item: PackageVersion) => {
    const confirmed = window.confirm(
      `למחוק את הטול „${item.name}”? הפעולה אינה הפיכה.`,
    );
    if (!confirmed) return;
    setError("");
    setMessage("");
    try {
      await api.deletePackage(item.id);
      if (editingId === item.id) reset();
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
    startNew,
    editingId,
    save,
    remove,
    inspect,
    insert,
  };
}

export type PackageCatalogController = ReturnType<typeof usePackageCatalog>;
