"use client";

import {
  Dispatch, SetStateAction, SyntheticEvent, useEffect, useState,
} from "react";
import { Database, LoaderCircle } from "lucide-react";
import { api } from "@/services/api";
import type { Evidence, EvidencePage } from "@/types";

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
      <EvidenceList runId={runId} items={items} />
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

function EvidenceList({ runId, items }: { runId: string; items: Evidence[] }) {
  return (
    <div className="evidence-list">
      {items.map((item) =>
        <EvidenceItem key={item.id} runId={runId} item={item} />)}
      {!items.length && <p>לא נשמרו ראיות לריצה זו.</p>}
    </div>
  );
}

function EvidenceItem({ runId, item }: { runId: string; item: Evidence }) {
  const [page, setPage] = useState<EvidencePage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async (offset: number) => {
    if (loading) return;
    setLoading(true); setError("");
    try {
      const next = await api.evidencePage(runId, item.id, offset);
      setPage((current) => !current || offset === 0
        ? next
        : { ...next, records: [...current.records, ...next.records] });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "טעינת הראיות נכשלה");
    } finally {
      setLoading(false);
    }
  };

  const open = (event: SyntheticEvent<HTMLDetailsElement>) => {
    if (event.currentTarget.open && !page) void load(0);
  };

  return (
    <details onToggle={open}>
      <summary><Database size={16} aria-hidden="true" />
        {item.step_key} · {item.row_count} רשומות
      </summary>
      {error && <p role="alert">{error}</p>}
      {page && <EvidenceTable records={page.records} />}
      {loading && <p className="loading-line">
        <LoaderCircle size={16} /> טוען ראיות…
      </p>}
      {page?.has_more && !loading &&
        <button type="button" onClick={() => void load(page.records.length)}>
          טעינת 100 רשומות נוספות
        </button>}
    </details>
  );
}

/** Raw records as a table. A package may omit a field on some rows, so the
    columns are the union across the page rather than the first record's keys —
    otherwise a later row's value would have no column to land in. */
function EvidenceTable({ records }: { records: Array<Record<string, unknown>> }) {
  const columns = Array.from(
    new Set(records.flatMap((record) => Object.keys(record))),
  );
  if (!columns.length) return <p className="evidence-empty">אין רשומות להצגה.</p>;
  return (
    <div className="evidence-table-scroll">
      <table className="evidence-table" dir="ltr">
        <thead>
          <tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr>
        </thead>
        <tbody>
          {records.map((record, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{formatCell(record[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A missing field and a present-but-empty one must not read alike, so an
    absent value renders as an em dash rather than a blank cell. Objects and
    arrays keep their JSON form — there is no flat rendering that stays exact. */
function formatCell(value: unknown) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
