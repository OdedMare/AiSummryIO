export const emptyPackage = {
  package_key: "", name: "", description: "", package_id: "",
  input_cube_name: "", input_cube_parameter: "", input_mode: "single",
  output_cube_name: "", query_name: "", agent_enabled: true,
  agent_instructions: "", output_schema: "{}", example_input: "[]",
  example_output: "[]",
};

export const emptyWorkflow = {
  workflow_key: "", name: "", description: "", role: "detail",
  agent_enabled: true, agent_id: "", system_prompt: "", output_schema: "",
  examples: "",
};

export const parseJson = <T,>(value: string, fallback: T): T =>
  (value.trim() ? JSON.parse(value) : fallback) as T;
