import { AlertTriangle, Sparkles } from "lucide-react";
import BrandMark from "@/components/AppShell/BrandMark";
import type {
  Citation, SummaryClaim, SummaryRun, SummarySection, SummarySkill,
} from "@/types";
import { CitationMarkers, CitedLine, CitedText } from "./CitationChip";
import { citationNumbers, trailingCitations } from "./citations";
import { SkillHint, SkillResults } from "./Skills";

export function EmptyWorkspace({ skills }: { skills: SummarySkill[] }) {
  return (
    <main id="main-workspace" className="workspace empty-workspace">
      <div className="empty-intro">
        <div className="empty-illustration"><BrandMark size={40} /></div>
        <span className="welcome-pill"><Sparkles size={14} />
          פשוט מתחילים ממזהה
        </span>
        <h1>כל מה שחשוב לדעת, <span className="hero-accent">בסיכום אחד
          ברור</span></h1>
        <p>הזינו מזהה בתיבה למטה. <b dir="ltr">SumOrAI</b> יאסוף את המידע,
          יסביר אותו בעברית ויראה על אילו מקורות הסתמך.</p>
      </div>
      <SkillHint skills={skills} />
    </main>
  );
}

/**
 * The thread's title, on the opening turn only.
 *
 * The status pill and the "x of y processes" readout moved to `AgentStatus`,
 * which says what the agent is doing in the user's terms. Keeping them here
 * too would state the same thing twice, once conversationally and once as a
 * job readout — and the job readout is the framing this is moving away from.
 * A finished turn needs no status at all: the answer is the status.
 */
export function RunHeader({ run }: { run: SummaryRun }) {
  return (
    <header className="workspace-header">
      <div>
        <h1>{run.kind === "full" ? "הסיכום המלא" : "תשובת המשך"}</h1>
      </div>
    </header>
  );
}

/** One continuous answer rather than a card per workflow. Sections are merged
    into the prose and reappear below as sources, so a reader follows a single
    thread instead of reassembling one from stacked panels. */
export function SummaryContent({
  run, activeCitationId, onSelectCitation,
}: {
  run: SummaryRun;
  /** The citation whose record is open, so its marker reads as pressed. */
  activeCitationId?: string | null;
  /** Opens a citation's exact record in the thread's evidence drawer. */
  onSelectCitation?: (citation: Citation) => void;
}) {
  const result = run.result;
  const sections = result?.sections ?? run.progress.sections ?? [];
  const synthesized = Boolean(result?.summary);
  /* Absent on a summary produced before citations existed, which is why every
     consumer below treats them as optional and renders plain text without
     them. */
  const claims = result?.claims ?? [];
  const citations = result?.citations ?? [];
  const active = activeCitationId ?? null;
  const select = onSelectCitation ?? (() => {});
  const cite = { claims, citations, activeId: active, onSelect: select };
  return (
    <>
      {run.error && <div className="error-banner" role="alert">{run.error}</div>}
      <article className="answer-body">
        {result?.headline && <p className="answer-headline">{result.headline}</p>}
        {synthesized
          ? <p><CitedText text={result?.summary ?? ""} {...cite} /></p>
          : <PendingAnswer sections={sections} />}
        {result?.coverage && <p className="answer-coverage">{result.coverage}</p>}
        <AnswerList items={result?.key_findings ?? []} cite={cite} />
        <AnswerList title="סיכונים" tone="risk" items={result?.risks ?? []}
          cite={cite} />
        {/* Gaps are statements about missing evidence, so there is nothing to
            cite them to. */}
        <AnswerList title="מידע חסר" tone="gap"
          items={result?.missing_data ?? []} />
        {result && <TracedSources result={result} activeId={active}
          onSelect={select} />}
        <Warnings sections={synthesized ? sections : []} />
      </article>
      <SkillResults items={result?.skill_results ?? []} />
    </>
  );
}

/** Sources traced to a claim whose sentence never appeared verbatim in the
    rendered text. Without this the claim would silently lose its citation,
    and every claim has to stay reachable from the answer. */
function TracedSources({
  result, activeId, onSelect,
}: {
  result: NonNullable<SummaryRun["result"]>;
  activeId: string | null;
  onSelect: (citation: Citation) => void;
}) {
  const trailing = trailingCitations(result);
  if (!trailing.length) return null;
  return (
    <p className="answer-traced-sources">
      מקורות נוספים לתשובה:{" "}
      <CitationMarkers citations={trailing}
        numbers={citationNumbers(result.citations ?? [])}
        activeId={activeId} onSelect={onSelect} />
    </p>
  );
}

/** Before synthesis finishes, `result` is null while sections stream in. Their
    summaries are the answer so far, so the prose assembles as they land rather
    than staying blank and popping in whole.

    The "still working" spinners that used to sit here now live in
    `AgentStatus`, which names each source as it arrives. Repeating them would
    put two live indicators on one turn saying the same thing. */
function PendingAnswer({ sections }: { sections: SummarySection[] }) {
  const arrived = sections.filter((section) => section.summary);
  if (!arrived.length) return null;
  return (
    <>
      {arrived.map((section) =>
        <p key={section.workflow_id}>{section.summary}</p>)}
    </>
  );
}

/** Findings, risks and gaps read as part of the answer, so they are plain
    lists in the flow — not tiles or bordered blocks beside it. */
interface CiteProps {
  claims: SummaryClaim[];
  citations: Citation[];
  activeId: string | null;
  onSelect: (citation: Citation) => void;
}

function AnswerList(
  { title, tone, items, cite }: {
    title?: string; tone?: string; items: string[]; cite?: CiteProps;
  },
) {
  if (!items.length) return null;
  return (
    <div className={`answer-list ${tone ?? ""}`}>
      {title && <h3>{title}</h3>}
      <ul>
        {items.map((item) => (
          <li key={item}>
            {cite ? <CitedLine line={item} {...cite} /> : item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Section warnings lost their card, so they collect here instead of vanishing:
    a partial source has to say so somewhere in the answer. */
function Warnings({ sections }: { sections: SummarySection[] }) {
  const items = sections.flatMap((section) =>
    section.warnings.map((warning) => ({
      key: `${section.workflow_id}:${warning}`,
      name: section.name,
      warning,
    })));
  const degraded = sections.some((section) => section.degraded);
  if (!items.length && !degraded) return null;
  return (
    <div className="answer-warnings" role="status">
      <h3><AlertTriangle size={15} aria-hidden="true" /> הסתייגויות</h3>
      <ul>
        {degraded && <li>חלק מהסיכום הופק ללא מודל השפה — ספירות בלבד.</li>}
        {items.map((item) =>
          <li key={item.key}><b>{item.name}:</b> {item.warning}</li>)}
      </ul>
    </div>
  );
}
