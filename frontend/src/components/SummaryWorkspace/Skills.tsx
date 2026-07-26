import {
  BriefcaseBusiness, CalendarDays, Check, GitCompareArrows, ListChecks,
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

export function SkillPicker({
  skills, selected, onToggle,
}: {
  skills: SummarySkill[];
  selected: string[];
  onToggle: (key: string) => void;
}) {
  if (!skills.length) return null;
  return (
    <section className="skill-picker" aria-labelledby="skill-picker-title">
      <header>
        <div><span className="eyebrow">לא חובה</span>
          <h2 id="skill-picker-title">מה תרצו לקבל מהסיכום?</h2>
          <p>כל Skill מפעיל ניתוח נוסף על המידע שנאסף.</p>
        </div>
        <span>{selected.length}/3 נבחרו</span>
      </header>
      <div className="skill-grid">
        {skills.map((skill) =>
          <SkillCard key={skill.content_key} skill={skill}
            active={selected.includes(skill.content_key)} onToggle={onToggle} />)}
      </div>
    </section>
  );
}

function SkillCard({
  skill, active, onToggle,
}: {
  skill: SummarySkill;
  active: boolean;
  onToggle: (key: string) => void;
}) {
  return (
    <button type="button" className={active ? "skill-card active" : "skill-card"}
      onClick={() => onToggle(skill.content_key)} aria-pressed={active}>
      <span className="skill-card-icon">
        <SkillIcon skillKey={skill.content_key} size={20} />
      </span>
      <span><strong>{skill.name}</strong><small>{skill.description}</small></span>
      <span className="skill-check" aria-hidden="true">
        {active && <Check size={15} />}
      </span>
    </button>
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
