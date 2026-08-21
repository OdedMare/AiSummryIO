import {
  AlertTriangle, Bot, CheckCircle2, MessagesSquare, Workflow,
} from "lucide-react";
import type {
  AgentPhase, SpecialistAnswer, SpecialistTrace, SummaryRun,
} from "@/types";

export default function AgentTrace({ run }: { run: SummaryRun }) {
  const trace = run.result?.agent_trace ?? run.progress.agent_trace;
  const quality = run.result?.quality;
  const telemetry = run.result?.telemetry;
  const decision = run.result?.route_decision;
  if (!trace?.specialists.length && !quality && !telemetry && !decision) return null;
  const active = run.status === "queued" || run.status === "running";
  return (
    <details className="agent-trace" open={active || undefined}>
      <summary>
        <Bot size={17} aria-hidden="true" />
        <span>איך התשובה נבנתה</span>
        <small>{trace
          ? phaseLabel(trace.phase, trace.rounds_used)
          : quality ? `ביטחון ${qualityLabel(quality.level)}` : "פרטי הריצה"}</small>
      </summary>
      {(quality || telemetry || decision) && <dl className="agent-run-insights">
        {quality && <div><dt>ביטחון</dt><dd>
          {Math.round(quality.score * 100)}% · {qualityLabel(quality.level)}
        </dd></div>}
        {decision && <div><dt>ניתוב</dt><dd>
          {decisionLabel(decision.action)} · {Math.round(decision.confidence * 100)}%
        </dd></div>}
        {telemetry && <div><dt>איסוף</dt><dd>
          {telemetry.workflow_count} Workflows · {telemetry.tool_calls} קריאות · {telemetry.evidence_rows} רשומות
        </dd></div>}
        {telemetry && <div><dt>זמן</dt><dd>
          {(telemetry.duration_ms / 1000).toLocaleString("he-IL", { maximumFractionDigits: 1 })} שנ׳
        </dd></div>}
      </dl>}
      {!!quality?.reasons.length && <p className="agent-trace-quality-note">
        {quality.reasons.join(" · ")}
      </p>}
      {!!trace?.specialists.length && <ol className="agent-trace-list">
        {trace.specialists.map((specialist) => (
          <Specialist key={specialist.agent_id} specialist={specialist} />
        ))}
      </ol>}
      {!!trace.missing_data?.length &&
        <div className="agent-trace-gaps" role="status">
          <AlertTriangle size={15} aria-hidden="true" />
          <span>{trace.missing_data.join(" · ")}</span>
        </div>}
    </details>
  );
}

function qualityLabel(level: "high" | "medium" | "low"): string {
  return level === "high" ? "גבוה" : level === "medium" ? "בינוני" : "נמוך";
}

function decisionLabel(action: string): string {
  if (action === "workflow") return "Workflow";
  if (action === "tool") return "טול";
  if (action === "use_cached") return "ראיות קיימות";
  return "בקשת הבהרה";
}

function Specialist({ specialist }: { specialist: SpecialistTrace }) {
  const complete = specialist.status === "completed";
  return (
    <li className={`agent-trace-specialist ${specialist.status}`}>
      <header>
        {complete
          ? <CheckCircle2 size={16} aria-hidden="true" />
          : specialist.status === "failed" || specialist.status === "partial"
            ? <AlertTriangle size={16} aria-hidden="true" />
            : <Bot size={16} aria-hidden="true" />}
        <strong>{specialist.name}</strong>
      </header>
      <p>{specialist.task}</p>
      <Selections specialist={specialist} />
      {specialist.answers.map((answer) => (
        <Answer key={`${answer.round}:${answer.question}`} answer={answer} />
      ))}
      {specialist.error && <p className="agent-trace-error" role="alert">
        {specialist.error}
      </p>}
    </li>
  );
}

function Selections({ specialist }: { specialist: SpecialistTrace }) {
  if (!specialist.workflow_keys.length && !specialist.skill_keys.length) return null;
  return (
    <dl className="agent-trace-selection">
      {!!specialist.workflow_keys.length && <div>
        <dt><Workflow size={13} aria-hidden="true" /> Workflows</dt>
        <dd dir="ltr">{specialist.workflow_keys.join(", ")}</dd>
      </div>}
      {!!specialist.skill_keys.length && <div>
        <dt><Bot size={13} aria-hidden="true" /> Skills</dt>
        <dd dir="ltr">{specialist.skill_keys.join(", ")}</dd>
      </div>}
    </dl>
  );
}

function Answer({ answer }: { answer: SpecialistAnswer }) {
  return (
    <section className={`agent-trace-answer ${answer.status}`}>
      <h4><MessagesSquare size={14} aria-hidden="true" /> שאלת המנהל</h4>
      <p>{answer.question}</p>
      <h4>תשובת המומחה</h4>
      <p>{answer.answer}</p>
      {!!answer.limitations.length &&
        <p className="agent-trace-limit">{answer.limitations.join(" · ")}</p>}
      {!!answer.evidence_ids.length && <div className="agent-trace-evidence">
        <span>ראיות:</span>
        {answer.evidence_ids.map((id) =>
          <code key={id} title={id} dir="ltr">{id.slice(0, 8)}</code>)}
      </div>}
    </section>
  );
}

function phaseLabel(phase: AgentPhase, rounds: number): string {
  if (phase === "delegating") return "בחירת מומחים";
  if (phase === "running_workflows") return "איסוף מידע";
  if (phase === "questioning") return `סבב העמקה ${rounds}`;
  if (phase === "synthesizing") return "חיבור התשובה";
  return rounds ? `הושלם לאחר ${rounds} סבבי העמקה` : "הושלם ללא סבב נוסף";
}
