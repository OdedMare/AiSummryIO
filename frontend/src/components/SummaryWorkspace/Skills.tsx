import {
  BriefcaseBusiness, CalendarDays, GitCompareArrows, ListChecks,
  ScanSearch, ShieldAlert, Sparkles, Users,
} from "lucide-react";
import type { SkillResult, SummarySkill } from "@/types";

const SkillIcon = ({ skillKey, size }: { skillKey: string; size: number }) => {
  if (skillKey.includes("executive")) return <BriefcaseBusiness size={size} />;
  if (skillKey.includes("risk")) return <ShieldAlert size={size} />;
  if (skillKey.includes("action")) return <ListChecks size={size} />;
  if (skillKey.includes("timeline")) return <CalendarDays size={size} />;
  if (skillKey.includes("contradiction")) return <GitCompareArrows size={size} />;
  if (skillKey.includes("entities")) return <Users size={size} />;
  if (skillKey.includes("evidence-quality")) return <ScanSearch size={size} />;
  return <Sparkles size={size} />;
};

/** Read-only reference for the `/name` commands available in the composer. */
export function SkillHint({ skills }: { skills: SummarySkill[] }) {
  if (!skills.length) return null;
  return (
    <section className="skill-hint" aria-labelledby="skill-hint-title">
      <header>
        <span className="eyebrow">לא חובה</span>
        <h2 id="skill-hint-title">רוצים ניתוח נוסף?</h2>
        <p>כתבו <code dir="ltr">/</code> בתיבת ההודעה ובחרו מהרשימה,
          למשל <span className="skill-command">/תקציר מנהלים</span>.</p>
      </header>
      <ul className="skill-hint-list">
        {skills.map((skill) =>
          <li key={skill.content_key}>
            <span className="skill-card-icon">
              <SkillIcon skillKey={skill.content_key} size={18} />
            </span>
            <span>
              <strong className="skill-command">/{skill.name}</strong>
              <small>{skill.description}</small>
            </span>
          </li>)}
      </ul>
    </section>
  );
}

export function SkillResults({ items }: { items: SkillResult[] }) {
  if (!items.length) return null;
  return (
    <section className="skill-results" aria-labelledby="skill-results-title">
      <header><span className="eyebrow">לפי הבחירה שלכם</span>
        <h2 id="skill-results-title">תוצרי ה־Skills</h2>
      </header>
      <div className="skill-result-grid">
        {items.map((item) => <SkillResultCard key={item.skill_key} item={item} />)}
      </div>
    </section>
  );
}

function SkillResultCard({ item }: { item: SkillResult }) {
  return (
    <article className="skill-result-card">
      <header><span><SkillIcon skillKey={item.skill_key} size={19} /></span>
        <h3>{item.name}</h3>
      </header>
      <p>{item.summary}</p>
      {!!item.items.length &&
        <ul>{item.items.map((entry) => <li key={entry}>{entry}</li>)}</ul>}
      {!!item.sources.length &&
        <small>מבוסס על: {item.sources.join(" · ")}</small>}
    </article>
  );
}
