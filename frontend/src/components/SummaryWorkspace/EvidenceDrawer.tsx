"use client";

import { Dispatch, SetStateAction, useEffect, useState } from "react";
import { Database, LoaderCircle } from "lucide-react";
import { api } from "@/services/api";
import type { Evidence } from "@/types";

type LoadedEvidence = { runId: string; items: Evidence[]; error: string };

export default function EvidenceDrawer({
  runId, open, evidenceIds, title,
}: {
  runId: string;
  open: boolean;
  /** When set, only these records show — a source chip opens its own evidence
      rather than the whole run's. */
  evidenceIds?: string[];
  title?: string;
}) {
  const [loaded, setLoaded] = useState<LoadedEvidence | null>(null);
  useEvidence(runId, open, setLoaded);
  if (!open) return null;
  const current = loaded?.runId === runId ? loaded : null;
  if (current?.error) return <p role="alert">{current.error}</p>;
  if (!current) return <p className="loading-line">
    <LoaderCircle size={16} /> טוען ראיות…
  </p>;
  const items = evidenceIds
    ? current.items.filter((item) => evidenceIds.includes(item.id))
    : current.items;
  return (
    <div className="evidence-panel">
      {title && <h3 className="evidence-title">{title}</h3>}
      <EvidenceList items={items} />
    </div>
  );
}

function useEvidence(
  runId: string,
  open: boolean,
  setLoaded: Dispatch<SetStateAction<LoadedEvidence | null>>,
) {
  useEffect(() => {
    if (!open) return;
    let current = true;
    api.evidence(runId)
      .then((items) => current &&
        setLoaded({ runId, items, error: "" }))
      .catch((reason) => current &&
        setLoaded({ runId, items: [], error: reason.message }));
    return () => { current = false; };
  }, [open, runId, setLoaded]);
}

function EvidenceList({ items }: { items: Evidence[] }) {
  return (
    <div className="evidence-list">
      {items.map((item) => (
        <details key={item.id}>
          <summary><Database size={16} aria-hidden="true" />
            {item.step_key} · {item.records.length} רשומות
          </summary>
          <pre dir="ltr">{JSON.stringify(item.records, null, 2)}</pre>
        </details>
      ))}
      {!items.length && <p>לא נשמרו ראיות לריצה זו.</p>}
    </div>
  );
}
