import { FormEvent, useState } from "react";
import { api } from "@/services/api";
import type {
  PackageVersion, WorkflowPlan, WorkflowStep, WorkflowVersion,
} from "@/types";
import { emptyWorkflow } from "../forms";
import {
  errorMessage,
  newStep,
  patchedStep,
  releaseDependents,
  toolOutputSchema,
  workflowForm,
  workflowPayload,
} from "./workflowModel";

export function useWorkflowEditor(
  packages: PackageVersion[],
  onRefresh: () => Promise<void>,
) {
  const [form, setForm] = useState(emptyWorkflow);
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  /* Which library row this form is editing, or "" for a new workflow. A
     workflow is one row, edited in place, so saving an edit has to update
     that row — posting again would be rejected as a duplicate key. */
  const [editingId, setEditingId] = useState("");
  const [error, setError] = useState("");
  const [libraryError, setLibraryError] = useState("");
  const [message, setMessage] = useState("");
  const [dryRunId, setDryRunId] = useState("");
  const [dryResult, setDryResult] = useState("");
  const [saving, setSaving] = useState(false);
  const [selectedKey, setSelectedKey] = useState("");

  const update = <Key extends keyof typeof emptyWorkflow>(
    key: Key, value: (typeof emptyWorkflow)[Key],
  ) => setForm((current) => ({ ...current, [key]: value }));

  const edit = (item: WorkflowVersion) => {
    setForm(workflowForm(item));
    setEditingId(item.id);
    setSteps(item.steps.map((step) => ({ ...step })));
    setDryResult("");
    setError("");
    setMessage("");
  };

  const addStep = () => setSteps((current) => {
    const step = newStep(current, packages);
    setSelectedKey(step.key);
    return [...current, step];
  });

  const updateStep = (index: number, patch: Partial<WorkflowStep>) =>
    setSteps((current) => current.map((step, position) =>
      position === index ? patchedStep(step, patch) : step));

  const removeStep = (index: number) =>
    setSteps((current) => releaseDependents(
      current.filter((_, position) => position !== index),
      current[index]?.key ?? "",
    ));

  const removeStepByKey = (key: string) => {
    setSteps((current) => current.some((step) => step.key === key)
      ? releaseDependents(current.filter((step) => step.key !== key), key)
      : current);
    setSelectedKey((selected) => (selected === key ? "" : selected));
  };

  const connectStep = (
    targetKey: string,
    source: string,
    inputField: string,
  ) => setSteps((current) => current.map((step) =>
    step.key === targetKey
      ? patchedStep(step, { input_source: source, input_field: inputField })
      : step));

  const disconnectStep = (targetKey: string) =>
    connectStep(targetKey, "workflow.id", "");

  /**
   * Save the form: update the workflow being edited, or create a new one.
   *
   * There is no publishing step, so a save takes effect immediately —
   * including on a route the agent is already selecting. `agent_enabled` is
   * an ordinary field on the form and rides along with the save.
   */
  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const payload = workflowPayload(form, steps);
      if (editingId) {
        await api.updateWorkflow(editingId, payload);
        setMessage("התהליך עודכן.");
      } else {
        await api.createWorkflow(payload);
        setMessage("התהליך נשמר.");
        reset();
      }
      await onRefresh();
    } catch (reason) {
      setError(errorMessage(reason, "השמירה נכשלה"));
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setForm(emptyWorkflow);
    setSteps([]);
    setEditingId("");
    setSelectedKey("");
  };
  /* Leaving an edit for a blank form. `reset` alone is what `save` calls
     after creating, where the success message has to survive. */
  const startNew = () => { reset(); setError(""); setMessage(""); };

  const remove = async (item: WorkflowVersion) => {
    const confirmed = window.confirm(
      `למחוק את התהליך „${item.name}”? הפעולה אינה הפיכה.`,
    );
    if (!confirmed) return;
    setLibraryError("");
    try {
      await api.deleteWorkflow(item.id);
      if (editingId === item.id) reset();
      await onRefresh();
    } catch (reason) {
      setLibraryError(errorMessage(reason, "המחיקה נכשלה"));
    }
  };

  const dryRun = async (id: string) => {
    if (!dryRunId.trim()) {
      setLibraryError("יש להזין מזהה בדיקה");
      return;
    }
    setDryResult("מריץ חבילות…");
    setLibraryError("");
    try {
      const result = await api.dryRun(id, dryRunId.trim());
      setDryResult(JSON.stringify(result, null, 2));
    } catch (reason) {
      setDryResult("");
      setLibraryError(errorMessage(reason, "הבדיקה נכשלה"));
    }
  };

  const loadPlan = (plan: WorkflowPlan) => {
    setForm((current) => ({
      ...current,
      name: plan.name || current.name,
      description: plan.description || current.description,
      role: plan.role || current.role,
      system_prompt: plan.system_prompt || current.system_prompt,
    }));
    if (plan.can_build) setSteps(plan.steps.map((step) => ({ ...step })));
    setMessage("הצעת הסוכן נטענה כטיוטה. יש לבדוק אותה לפני השמירה.");
  };

  const loadPlanSteps = (plan: WorkflowPlan) => {
    if (!plan.can_build) return;
    setSteps(plan.steps.map((step) => ({ ...step })));
    setSelectedKey("");
    setMessage("שלבי הסוכן נטענו לקנבס. יש לבדוק את החיבורים לפני השמירה.");
  };

  const createFromTool = (item: PackageVersion) => {
    setForm({
      ...emptyWorkflow,
      name: item.name,
      description: item.description,
      role: "detail",
      output_schema: JSON.stringify(toolOutputSchema(item), null, 2),
      examples: "[]",
    });
    const step: WorkflowStep = {
      key: "step1",
      name: item.name,
      package_version_id: item.id,
      depends_on: [],
      input_source: "workflow.id",
      input_field: "",
      input_value: "",
      summary_prompt: "",
    };
    setSteps([step]);
    setSelectedKey(step.key);
    setDryResult("");
    setError("");
    setMessage(
      `נוצרה טיוטת תהליך עם הטול „${item.name}” וחוזה הפלט שלו. בדקו ושמרו.`,
    );
  };

  return {
    form,
    steps,
    error,
    message,
    dryRunId,
    setDryRunId,
    dryResult,
    saving,
    libraryError,
    selectedKey,
    setSelectedKey,
    update,
    edit,
    addStep,
    updateStep,
    removeStep,
    removeStepByKey,
    connectStep,
    disconnectStep,
    save,
    remove,
    dryRun,
    loadPlan,
    loadPlanSteps,
    createFromTool,
    reset,
    startNew,
    editingId,
  };
}

export type WorkflowEditorController = ReturnType<typeof useWorkflowEditor>;
