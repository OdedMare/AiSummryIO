"use client";

import {
  AlertTriangle, ArrowRight, Beaker, LoaderCircle, Plus, RefreshCw,
} from "lucide-react";
import type { EvaluationBatch, SummaryAgent, SummarySkill } from "@/types";
import EvaluationResults from "./EvaluationResults";
import EvaluationSetup from "./EvaluationSetup";
import { useEvaluation } from "./useEvaluation";

export default function EvaluationPanel({
  skills, agents, projectId, onClose,
}: {
  skills: SummarySkill[];
  agents: SummaryAgent[];
  projectId: string;
  onClose: () => void;
}) {
  const evaluation = useEvaluation();
  return (
    <div className="studio-page evaluation-page">
      <header className="studio-page-header">
        <button type="button" className="studio-back" onClick={onClose}>
          <ArrowRight size={17} /> חזרה לשיחה</button>
        <span className="modal-icon"><Beaker size={20} /></span>
        <div><span className="studio-kicker">Quality workspace</span>
          <h2>Evaluation</h2></div>
        <button type="button" className="studio-refresh"
          onClick={() => void evaluation.refresh()}>
          <RefreshCw size={16} /> רענון</button>
      </header>
      <div className="evaluation-body">
        <EvaluationHistory evaluation={evaluation} />
        <section className="evaluation-main">
          {evaluation.loading
            ? <p className="loading-line"><LoaderCircle className="spin" /> טוען…</p>
            : evaluation.selectedId
              ? <EvaluationResults evaluation={evaluation} />
              : <>
                {evaluation.error && <p className="form-error evaluation-load-error"
                  role="alert"><AlertTriangle size={17} /> {evaluation.error}</p>}
                <EvaluationSetup skills={skills} agents={agents}
                  projectId={projectId}
                  activeBatch={evaluation.activeBatch}
                  onCreated={evaluation.created} />
              </>}
        </section>
      </div>
    </div>
  );
}

function EvaluationHistory({ evaluation }: { evaluation: ReturnType<typeof useEvaluation> }) {
  return <aside className="evaluation-history">
    <header><div><h2>הרצות</h2><span>{evaluation.batches.length}</span></div>
      <button type="button" onClick={() => evaluation.selectBatch(null)}
        aria-label="יצירת Evaluation חדש"><Plus size={16} /> חדש</button></header>
    <nav aria-label="היסטוריית Evaluation">
      {evaluation.batches.map((batch) => <HistoryItem key={batch.id} batch={batch}
        active={evaluation.selectedId === batch.id}
        onClick={() => evaluation.selectBatch(batch.id)} />)}
      {!evaluation.batches.length && <p>הריצות יופיעו כאן.</p>}
    </nav>
  </aside>;
}

function HistoryItem({
  batch, active, onClick,
}: {
  batch: EvaluationBatch;
  active: boolean;
  onClick: () => void;
}) {
  const done = batch.completed + batch.partial + batch.failed + batch.stopped;
  return <button type="button" className={active ? "active" : ""}
    aria-current={active ? "page" : undefined} onClick={onClick}>
    <span className={`history-status ${batch.status}`} aria-hidden="true" />
    <span><strong>{batch.label}</strong><small>
      {BATCH_STATUS[batch.status] ?? batch.status} · {done}/{batch.total} ·{" "}
      {new Date(batch.created_at).toLocaleDateString("he-IL")}</small></span>
  </button>;
}

const BATCH_STATUS: Record<string, string> = {
  running: "רץ", pausing: "מושהה בקרוב", paused: "מושהה",
  stopping: "עוצר", stopped: "נעצר", completed: "הושלם",
};
