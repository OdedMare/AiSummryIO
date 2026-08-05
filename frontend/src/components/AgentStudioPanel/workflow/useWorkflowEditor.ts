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
  const [error, setError] = useState("");
  const [libraryError, setLibraryError] = useState("");
  const [message, setMessage] = useState("");
  const [dryRunId, setDryRunId] = useState("");
  const [dryResult, setDryResult] = useState("");
  const [saving, setSaving] = useState(false);
  const [selectedKey, setSelectedKey] = useState("");

  const update = (key: keyof typeof emptyWorkflow, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const edit = (item: WorkflowVersion) => {
    setForm(workflowForm(item));
    setSteps(item.steps.map((step) => ({ ...step })));
    setDryResult("");
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

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await api.createWorkflow(workflowPayload(form, steps));
      setMessage("נשמרה טיוטת תהליך חדשה.");
      setForm(emptyWorkflow);
      setSteps([]);
      await onRefresh();
    } catch (reason) {
      setError(errorMessage(reason, "השמירה נכשלה"));
    } finally {
      setSaving(false);
    }
  };

  const publish = async (id: string) => {
    setLibraryError("");
    try {
      await api.publishWorkflow(id);
      await onRefresh();
    } catch (reason) {
      setLibraryError(errorMessage(reason, "הפרסום נכשל"));
    }
  };

  const reset = () => {
    setForm(emptyWorkflow);
    setSteps([]);
  };

  const remove = async (item: WorkflowVersion) => {
    const confirmed = window.confirm(
      `למחוק את התהליך „${item.name}” על כל הגרסאות שלו? הפעולה אינה הפיכה.`,
    );
    if (!confirmed) return;
    setLibraryError("");
    try {
      await api.deleteWorkflow(item.id);
      if (form.workflow_key === item.workflow_key) reset();
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
    publish,
    remove,
    dryRun,
    loadPlan,
    loadPlanSteps,
    createFromTool,
    reset,
  };
}

export type WorkflowEditorController = ReturnType<typeof useWorkflowEditor>;
