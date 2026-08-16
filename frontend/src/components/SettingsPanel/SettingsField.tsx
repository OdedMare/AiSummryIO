import type { SettingsController } from "./useSettings";

type FieldProps = {
  type?: string;
  optional?: string;
  placeholder?: string;
  ltr?: boolean;
  list?: string;
  min?: string;
  max?: string;
  step?: string;
};

export function SettingsField({
  settings, name, label, ...props
}: FieldProps & {
  settings: SettingsController;
  name: string;
  label: string;
}) {
  const secret = props.type === "password";
  const saved = secret && settings.secretSaved(name);
  return (
    <>
      <label className="field-label" htmlFor={`set-${name}`}>
        {label}
        {props.optional && <span className="optional"> ({props.optional})</span>}
        {saved && <span className="key-hint"> (נשמר)</span>}
      </label>
      <input id={`set-${name}`} className="settings-input"
        type={props.type ?? "text"} dir={props.ltr === false ? "auto" : "ltr"}
        list={props.list} min={props.min} max={props.max} step={props.step}
        placeholder={saved ? "השאירו ריק כדי לשמור את הערך הנוכחי" :
          props.placeholder}
        value={saved ? "" : settings.text(name)}
        onChange={(event) => settings.set(
          name, inputValue(event.target.value, props.type)
        )} />
    </>
  );
}

export function SettingsToggle({
  settings, name, label, optional,
}: {
  settings: SettingsController;
  name: string;
  label: string;
  optional?: string;
}) {
  return (
    <label className="field-label">
      <input type="checkbox" checked={settings.checked(name)}
        onChange={(event) => settings.set(name, event.target.checked)} />
      {label}
      {optional && <span className="optional"> ({optional})</span>}
    </label>
  );
}

function inputValue(value: string, type?: string) {
  if (type !== "number") return value;
  return value === "" ? null : Number(value);
}
