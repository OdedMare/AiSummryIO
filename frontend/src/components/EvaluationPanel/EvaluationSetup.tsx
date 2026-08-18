"use client";

import type { FormEvent } from "react";
import { useMemo, useRef, useState } from "react";
import {
  FileSpreadsheet, Layers3, LoaderCircle, Play, Server, Upload,
} from "lucide-react";
import { api } from "@/services/api";
import type { EvaluationBatch, SummaryAgent, SummarySkill } from "@/types";

export default function EvaluationSetup({
  skills, agents, projectId, activeBatch, onCreated,
}: {
  skills: SummarySkill[];
  agents: SummaryAgent[];
  projectId: string;
  activeBatch: EvaluationBatch | null;
  onCreated: (batch: EvaluationBatch) => Promise<void>;
}) {
  const [label, setLabel] = useState("");
  const [question, setQuestion] = useState("");
  const [rootIds, setRootIds] = useState("");
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [cooldown, setCooldown] = useState(0);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [importNote, setImportNote] = useState("");
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const ids = useMemo(
    () => rootIds.split(/\r?\n/).map((value) => value.trim()).filter(Boolean),
    [rootIds],
  );

  const toggleSkill = (key: string) => {
    setSelectedSkills((current) => current.includes(key)
      ? current.filter((item) => item !== key)
      : current.length < 3 ? [...current, key] : current);
  };

  const importFile = async (file?: File) => {
    if (!file) return;
    setImporting(true); setError(""); setWarnings([]);
    try {
      const imported = await api.importEvaluation(file);
      setRootIds(imported.root_ids.join("\n"));
      setWarnings(imported.warnings);
      setImportNote(
        `${imported.root_ids.length.toLocaleString("he-IL")} מזהים נטענו ` +
        `מהגיליון “${imported.sheet}”, עמודה ${imported.column}.`,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "קריאת הקובץ נכשלה");
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError("");
    if (!label.trim()) return setError("יש לתת שם לריצה");
    if (!question.trim()) return setError("יש להזין שאלה משותפת");
    if (!ids.length) return setError("יש להדביק או להעלות לפחות root_id אחד");
    if (activeBatch) return setError("כבר קיימת ריצה פעילה או מושהית");
    setSubmitting(true);
    try {
      const created = await api.createEvaluation({
        project_id: projectId,
        label: label.trim(), root_ids: ids, question: question.trim(),
        skill_keys: selectedSkills, agent_keys: selectedAgents,
        cooldown_seconds: cooldown,
      });
      await onCreated(created);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "יצירת הריצה נכשלה");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="evaluation-setup" id="main-workspace">
      <header><span className="eyebrow">Batch חדש</span>
        <h1>בדיקת סיכומים על קבוצת מזהים</h1>
        <p>מגדירים פעם אחת, עוקבים אחרי כל תוצאה ובודקים את איכות הסיכומים.</p>
        <div className="evaluation-assurances" aria-label="מאפייני ההרצה">
          <span><Server size={16} /><b>רץ בשרת</b> גם כשהדפדפן סגור</span>
          <span><Layers3 size={16} /><b>עד 3</b> סיכומים במקביל</span>
          <span><FileSpreadsheet size={16} /><b>עד 10,000</b> מזהים</span>
        </div>
      </header>
      {activeBatch && <p className="evaluation-notice" role="status">
        הריצה “{activeBatch.label}” פעילה. ניתן להכין את הטופס, אך להתחיל רק
        לאחר שתסתיים או תיעצר.
      </p>}
      <form className="evaluation-form" onSubmit={submit}>
        <label><span>שם הריצה <b aria-hidden="true">*</b></span>
          <input value={label} onChange={(event) => setLabel(event.target.value)}
            placeholder="לדוגמה: prompt-v3 · אוגוסט" maxLength={5000} required />
        </label>
        <label className="evaluation-question"><span>שאלה משותפת{" "}
          <b aria-hidden="true">*</b></span>
          <textarea value={question}
            onChange={(event) => setQuestion(event.target.value)} rows={3}
            placeholder="איזה סיכום להפיק עבור כל מזהה?" maxLength={5000} required />
        </label>
        <section className="evaluation-identifiers" aria-labelledby="ids-title">
          <header><div><span id="ids-title">מזהים <b aria-hidden="true">*</b></span>
            <small>מזהה אחד בכל שורה; כפילויות נשמרות כריצות נפרדות.</small>
          </div>
            <button className="secondary-button" type="button"
              onClick={() => fileRef.current?.click()}
              disabled={submitting || importing}>
              {importing ? <LoaderCircle className="spin" size={17} /> :
                <Upload size={17} />} {importing ? "טוען…" : "העלאת Excel"}
            </button>
            <input ref={fileRef} className="visually-hidden" type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => void importFile(event.target.files?.[0])} />
          </header>
          <textarea dir="ltr" value={rootIds}
            aria-labelledby="ids-title"
            onChange={(event) => { setRootIds(event.target.value); setImportNote(""); }}
            rows={10} placeholder={"ROOT-001\nROOT-002\nROOT-003"} required />
          <footer><span><FileSpreadsheet size={15} />
            {ids.length.toLocaleString("he-IL")} מזהים</span>
            {importNote && <span role="status">{importNote}</span>}</footer>
          {warnings.map((warning) => <p className="warning-box" key={warning}>
            {warning}</p>)}
        </section>
        {!!skills.length && <fieldset className="evaluation-skills">
          <legend>Skills אופציונליים <small>עד 3</small></legend>
          <div>{skills.map((skill) => <label key={skill.content_key}
            className={selectedSkills.includes(skill.content_key) ? "selected" : ""}>
            <input type="checkbox"
              checked={selectedSkills.includes(skill.content_key)}
              disabled={!selectedSkills.includes(skill.content_key) &&
                selectedSkills.length >= 3}
              onChange={() => toggleSkill(skill.content_key)} />
            <span><strong>{skill.name}</strong><small>{skill.description}</small></span>
          </label>)}</div>
        </fieldset>}
        {!!agents.length && <fieldset className="evaluation-skills evaluation-agents">
          <legend>Agents להרצה <small>ללא הגבלה</small></legend>
          <p>ללא בחירה המערכת מנתבת אוטומטית. בחירה ידנית מריצה את כל הסוכנים שסומנו.</p>
          <div>{agents.map((agent) => <label key={agent.content_key}
            className={selectedAgents.includes(agent.content_key) ? "selected" : ""}>
            <input type="checkbox"
              checked={selectedAgents.includes(agent.content_key)}
              onChange={() => setSelectedAgents((current) =>
                current.includes(agent.content_key)
                  ? current.filter((item) => item !== agent.content_key)
                  : [...current, agent.content_key])} />
            <span><strong>{agent.name}</strong><small>{agent.description}</small></span>
          </label>)}</div>
        </fieldset>}
        <fieldset className="evaluation-cooldown">
          <legend>Cooldown בין התחלות</legend>
          <div className="cooldown-presets">
            {[0, 30, 60, 120].map((value) => <button type="button" key={value}
              className={cooldown === value ? "active" : ""}
              aria-pressed={cooldown === value}
              onClick={() => setCooldown(value)}>{cooldownLabel(value)}</button>)}
          </div>
          <label><span>ערך מותאם בשניות</span>
            <input type="number" min={0} max={3600} value={cooldown}
              onChange={(event) => setCooldown(Math.max(0,
                Math.min(3600, Number(event.target.value) || 0)))} /></label>
          <small>עד שלוש ריצות במקביל; ה־cooldown מפריד בין זמני ההתחלה.</small>
        </fieldset>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button evaluation-start" type="submit"
          disabled={submitting || importing || !!activeBatch}>
          {submitting ? <LoaderCircle className="spin" size={18} /> :
            <Play size={18} />} {submitting ? "מתחיל…" : "התחלת Evaluation"}
        </button>
      </form>
    </main>
  );
}

function cooldownLabel(seconds: number) {
  if (!seconds) return "ללא";
  return seconds < 60 ? `${seconds} שנ׳` : `${seconds / 60} דק׳`;
}
