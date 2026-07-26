"use client";

import { useState } from "react";
import {
  AlertTriangle, CheckCircle2, ChevronDown, ChevronUp,
} from "lucide-react";
import type { SummarySection } from "@/types";

export default function SectionCard({ section }: { section: SummarySection }) {
  const [open, setOpen] = useState(false);
  const Icon = section.status === "completed" ? CheckCircle2 : AlertTriangle;
  return (
    <article className="summary-section">
      <button className="section-toggle" type="button"
        onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <span className={`section-status ${section.status}`}>
          <Icon size={18} aria-hidden="true" />
        </span>
        <span><strong>{section.name}</strong>
          <small>{section.status === "completed" ? "הושלם" : "כיסוי חלקי"}</small>
        </span>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>
      <p>{section.summary}</p>
      {open && <SectionDetails section={section} />}
    </article>
  );
}

function SectionDetails({ section }: { section: SummarySection }) {
  return (
    <div className="section-details">
      {!!section.facts.length &&
        <ul>{section.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>}
      {!!section.warnings.length &&
        <div className="warning-box" role="status">
          {section.warnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>}
    </div>
  );
}
