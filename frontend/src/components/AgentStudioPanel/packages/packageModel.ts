import type {
  Dispatch,
  DragEvent,
  SetStateAction,
} from "react";
import type {
  PackageInspection,
  PackageVersion,
  ToolPlanDraft,
} from "@/types";
import { emptyPackage, parseJson } from "../forms";

export type PackageForm = typeof emptyPackage;
export type FieldTarget =
  "description" | "agent_instructions" | "output_schema" | "example_output";
export type SchemaField = {
  name: string;
  type: string;
  description: string;
  listened: boolean;
};
export type UpdatePackage = <Key extends keyof PackageForm>(
  key: Key,
  value: PackageForm[Key],
) => void;

export const FIELD_MIME = "application/x-aisummry-field";

export function packageForm(item: PackageVersion): PackageForm {
  return {
    package_key: item.package_key,
    name: item.name,
    description: item.description,
    package_id: item.package_id,
    input_cube_name: item.input_cube_name,
    input_cube_parameter: item.input_cube_parameter,
    input_mode: item.input_mode,
    output_cube_name: item.output_cube_name,
    query_name: item.query_name,
    agent_enabled: item.agent_enabled,
    agent_instructions: item.agent_instructions,
    output_schema: JSON.stringify(item.output_schema || {}, null, 2),
    example_input: JSON.stringify(item.example_input, null, 2),
    example_output: JSON.stringify(item.example_output, null, 2),
  };
}

export function packagePayload(form: PackageForm) {
  return {
    ...form,
    package_key: form.package_key || undefined,
    output_schema: parseJson<Record<string, unknown>>(form.output_schema, {}),
    example_input: parseJson<string[]>(form.example_input, []),
    example_output: parseJson<Array<Record<string, unknown>>>(
      form.example_output,
      [],
    ),
  };
}

export function connectionDraft(form: PackageForm): Partial<ToolPlanDraft> {
  return {
    package_key: form.package_key,
    package_id: form.package_id,
    input_cube_name: form.input_cube_name,
    input_cube_parameter: form.input_cube_parameter,
    output_cube_name: form.output_cube_name,
    input_mode: form.input_mode === "many"
      ? "many"
      : form.input_mode === "single" ? "single" : "",
    query_name: form.query_name,
  };
}

export function fieldPreview(value: string | boolean): string {
  if (typeof value !== "string" || !value) return "—";
  const flat = value.replace(/\s+/g, " ").trim();
  return flat.length > 80 ? `${flat.slice(0, 80)}…` : flat;
}

export function inspectionDisabled(
  form: PackageForm,
  inspectId: string,
  inspecting: boolean,
) {
  return inspecting || !inspectId.trim() || !form.name.trim()
    || !form.package_id.trim() || !form.input_cube_name.trim()
    || !form.input_cube_parameter.trim() || !form.output_cube_name.trim();
}

export function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}

export function schemaFields(value: string): SchemaField[] {
  try {
    const schema = JSON.parse(value) as {
      properties?: Record<string, unknown>;
    };
    return Object.entries(schema.properties ?? {}).map(([name, raw]) => {
      const definition = (
        raw && typeof raw === "object" ? raw : {}
      ) as Record<string, unknown>;
      const type = Array.isArray(definition.type)
        ? definition.type.join(" / ")
        : String(definition.type ?? "unknown");
      return {
        name,
        type,
        description: typeof definition.description === "string"
          ? definition.description
          : "",
        listened: definition["x-summary"] !== false,
      };
    });
  } catch {
    return [];
  }
}

export function setFieldPolicy(
  value: string,
  field: string,
  listened: boolean,
) {
  const schema = parseJson<Record<string, unknown>>(value, {});
  const properties = (
    schema.properties && typeof schema.properties === "object"
      ? schema.properties
      : {}
  ) as Record<string, unknown>;
  const current = properties[field];
  properties[field] = {
    ...(current && typeof current === "object" ? current : {}),
    "x-summary": listened,
  };
  return JSON.stringify({ ...schema, properties }, null, 2);
}

export function allowFieldDrop(event: DragEvent<HTMLTextAreaElement>) {
  if (event.dataTransfer.types.includes(FIELD_MIME)) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }
}

function draggedField(event: DragEvent<HTMLTextAreaElement>) {
  return event.dataTransfer.getData(FIELD_MIME);
}

export function dropTextField(
  event: DragEvent<HTMLTextAreaElement>,
  target: "description" | "agent_instructions",
  setForm: Dispatch<SetStateAction<PackageForm>>,
) {
  const field = draggedField(event);
  if (!field) return;
  event.preventDefault();
  const start = event.currentTarget.selectionStart;
  const end = event.currentTarget.selectionEnd;
  setForm((current) => ({
    ...current,
    [target]: insertText(current[target], `\`${field}\``, start, end),
  }));
}

export function dropJsonField(
  event: DragEvent<HTMLTextAreaElement>,
  target: "output_schema" | "example_output",
  inspection: PackageInspection | null,
  setForm: Dispatch<SetStateAction<PackageForm>>,
) {
  const field = draggedField(event);
  if (!field) return;
  event.preventDefault();
  setForm((current) => insertField(current, field, target, inspection));
}

export function insertField(
  form: PackageForm,
  field: string,
  target: FieldTarget,
  inspection: PackageInspection | null,
): PackageForm {
  if (target === "description" || target === "agent_instructions") {
    return { ...form, [target]: appendText(form[target], `\`${field}\``) };
  }
  if (target === "output_schema") {
    return {
      ...form,
      output_schema: setFieldPolicy(form.output_schema, field, true),
    };
  }
  const rows = parseJson<Array<Record<string, unknown>>>(
    form.example_output,
    [],
  );
  const sample = inspection?.records[0]?.[field] ?? null;
  const [first = {}, ...rest] = rows;
  return {
    ...form,
    example_output: JSON.stringify([{ ...first, [field]: sample }, ...rest], null, 2),
  };
}

function appendText(value: string, token: string) {
  return value.trimEnd() + (value.trim() ? " " : "") + token;
}

function insertText(value: string, token: string, start: number, end: number) {
  const before = value.slice(0, start);
  const after = value.slice(end);
  const leading = before && !/\s$/.test(before) ? " " : "";
  const trailing = after && !/^\s/.test(after) ? " " : "";
  return before + leading + token + trailing + after;
}

export function emptyJsonArray(value: string) {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) && parsed.length === 0;
  } catch {
    return false;
  }
}
