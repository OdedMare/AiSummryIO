"use client";

import { useState } from "react";
import {
  AlertTriangle, CalendarDays, CheckCircle2, ChevronLeft, ChevronRight,
  CircleStop, Download, Layers3, LoaderCircle, Pause, Play, RefreshCw,
  Search, Star, Timer, Trash2,
} from "lucide-react";
import { SummaryContent } from "@/components/SummaryWorkspace/RunContent";
import { api } from "@/services/api";
import type {
  EvaluationBatch, EvaluationCase, EvaluationCaseDetail, SummaryRun,
} from "@/types";
import type { EvaluationController } from "./useEvaluation";

const STATUS: Record<string, string> = {
  running: "רץ", pausing: "מסיים פעילים לקראת השהיה", paused: "מושהה",
  stopping: "עוצר", stopped: "נעצר", completed: "הושלם",
  pending: "ממתין", queued: "בתור", partial: "הושלם חלקית", failed: "נכשל",
};

export default function EvaluationResults({
  evaluation,
}: {
  evaluation: EvaluationController;
}) {
  const batch = evaluation.batch;
  if (!batch) return <p className="loading-line"><LoaderCircle className="spin" />
    טוען ריצה…</p>;
  const done = batch.completed + batch.partial + batch.failed + batch.stopped;
  const progress = batch.total ? Math.round(done / batch.total * 100) : 0;
  return (
    <main className="evaluation-results" id="main-workspace">
      <BatchHeader batch={batch} evaluation={evaluation} />
      <Overview batch={batch} done={done} progress={progress} />
      {evaluation.error && <p className="form-error evaluation-error" role="alert">
        <AlertTriangle size={17} /> {evaluation.error}</p>}
      <div className="evaluation-review-layout">
        <CasesList evaluation={evaluation} />
        <CaseDetail evaluation={evaluation} />
      </div>
    </main>
  );
}

function BatchHeader({
  batch, evaluation,
}: {
  batch: EvaluationBatch;
  evaluation: EvaluationController;
}) {
  const active = ["running", "pausing", "paused", "stopping"].includes(batch.status);
  const exportFile = async () => {
    try {
      const blob = await api.exportEvaluation(batch.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `${safeName(batch.label)}.xlsx`; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (reason) {
      evaluation.reportError(
        reason instanceof Error ? reason.message : "ייצוא ה-Excel נכשל",
      );
    }
  };
  const stop = () => {
    if (!window.confirm("לעצור את הריצה? פריטים שטרם התחילו לא יורצו.")) return;
    void evaluation.action(() => api.stopEvaluation(batch.id), "עצירת הריצה נכשלה");
  };
  return (
    <header className="evaluation-results-header">
      <div className="evaluation-title-block"><div className="evaluation-title-labels">
        <span className={`evaluation-status ${batch.status}`}>
          {STATUS[batch.status] ?? batch.status}</span>
        <span className="evaluation-batch-label">Evaluation batch</span>
      </div>
        <h1>{batch.label}</h1>
        <p>{batch.question}</p>
        <div className="evaluation-meta">
          <span><CalendarDays size={14} />
            {new Date(batch.created_at).toLocaleString("he-IL")}</span>
          <span><Timer size={14} /> Cooldown: {batch.cooldown_seconds} שנ׳</span>
          {!!batch.skill_keys.length && <span><Layers3 size={14} />
            {batch.skill_keys.join(" · ")}</span>}
        </div>
      </div>
      <nav aria-label="פעולות ריצה">
        {batch.status === "running" && <button className="secondary-button"
          type="button" disabled={evaluation.busy}
          onClick={() => void evaluation.action(
            () => api.pauseEvaluation(batch.id), "השהיית הריצה נכשלה",
          )}><Pause size={17} /> השהיה</button>}
        {batch.status === "paused" && <button className="primary-button"
          type="button" disabled={evaluation.busy}
          onClick={() => void evaluation.action(
            () => api.resumeEvaluation(batch.id), "חידוש הריצה נכשל",
          )}><Play size={17} /> המשך</button>}
        {active && !["stopping", "stopped"].includes(batch.status) &&
          <button className="evaluation-stop" type="button"
            disabled={evaluation.busy} onClick={stop}>
            <CircleStop size={17} /> עצירה</button>}
        {!!batch.failed && !active && <button className="secondary-button"
          type="button" disabled={evaluation.busy}
          onClick={() => void evaluation.retryFailed()}>
          <RefreshCw size={17} /> הרצת נכשלים</button>}
        <button className="secondary-button" type="button" onClick={exportFile}>
          <Download size={17} /> Excel</button>
        {!active && <button className="evaluation-delete" type="button"
          disabled={evaluation.busy} onClick={() => void evaluation.remove()}>
          <Trash2 size={17} /> מחיקת סשן</button>}
      </nav>
    </header>
  );
}

function Overview({
  batch, done, progress,
}: {
  batch: EvaluationBatch;
  done: number;
  progress: number;
}) {
  return <section className="evaluation-overview" aria-labelledby="progress-title">
    <header><div><span id="progress-title">התקדמות הריצה</span>
      <strong>{progress}%</strong></div>
      <p aria-live="polite">{done.toLocaleString("he-IL")} מתוך{" "}
        {batch.total.toLocaleString("he-IL")} תוצאות</p></header>
    <div className="evaluation-progress" role="progressbar"
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}
      aria-label={`התקדמות ${progress}%`}>
      <span style={{ width: `${progress}%` }} />
    </div>
    <Stats batch={batch} />
  </section>;
}

function Stats({ batch }: { batch: EvaluationBatch }) {
  const stats = [
    ["הושלמו", batch.completed, "success", <CheckCircle2 key="done" />],
    ["חלקיים", batch.partial, "warning", <AlertTriangle key="partial" />],
    ["נכשלו", batch.failed, "danger", <CircleStop key="failed" />],
    ["רצים / בתור", batch.running + batch.queued, "active",
      <LoaderCircle key="active" />],
    ["ציון ממוצע", batch.average_rating ?? "—", "rating", <Star key="rating" />],
  ];
  return <section className="evaluation-stats" aria-label="נתוני הריצה">
    {stats.map(([label, value, tone, icon]) => <article key={String(label)}
      className={String(tone)}><i aria-hidden="true">{icon}</i><div>
        <span>{label}</span><strong>{value}</strong></div></article>)}
  </section>;
}

function CasesList({ evaluation }: { evaluation: EvaluationController }) {
  const pageCount = Math.max(1, Math.ceil(evaluation.cases.total / evaluation.cases.limit));
  return (
    <section className="evaluation-cases" aria-labelledby="cases-title">
      <header><div><h2 id="cases-title">תוצאות</h2>
        <span>{evaluation.cases.total.toLocaleString("he-IL")}</span></div>
        <label className="evaluation-search"><Search size={16} />
          <span className="visually-hidden">חיפוש לפי מזהה</span>
          <input dir="ltr" value={evaluation.search} placeholder="חיפוש root_id"
            onChange={(event) => evaluation.setSearch(event.target.value)} /></label>
        <label><span className="visually-hidden">סינון לפי סטטוס</span>
          <select value={evaluation.status}
            onChange={(event) => evaluation.setStatus(event.target.value)}>
            <option value="">כל הסטטוסים</option>
            {Object.entries(STATUS).filter(([key]) =>
              !["pausing", "paused", "stopping"].includes(key))
              .map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></label>
      </header>
      <div className="evaluation-table-wrap">
        <table><thead><tr><th>#</th><th>root_id</th><th>סטטוס</th>
          <th>זמן</th><th>ציון</th></tr></thead>
          <tbody>{evaluation.cases.items.map((item) =>
            <CaseRow key={item.id} item={item} evaluation={evaluation} />)}</tbody>
        </table>
        {!evaluation.cases.items.length && <p className="evaluation-empty">
          לא נמצאו תוצאות לפי הסינון.</p>}
      </div>
      <footer className="evaluation-pagination">
        <button type="button" aria-label="העמוד הקודם"
          disabled={evaluation.page === 0}
          onClick={() => evaluation.setPage(Math.max(0, evaluation.page - 1))}>
          <ChevronRight size={18} /></button>
        <span>עמוד {evaluation.page + 1} מתוך {pageCount}</span>
        <button type="button" aria-label="העמוד הבא"
          disabled={evaluation.page + 1 >= pageCount}
          onClick={() => evaluation.setPage(evaluation.page + 1)}>
          <ChevronLeft size={18} /></button>
      </footer>
    </section>
  );
}

function CaseRow({
  item, evaluation,
}: {
  item: EvaluationCase;
  evaluation: EvaluationController;
}) {
  return <tr className={evaluation.selectedCaseId === item.id ? "selected" : ""}>
    <td>{item.position}</td>
    <td><button type="button" dir="ltr" title={item.root_id}
      aria-label={`פתיחת תוצאה עבור ${item.root_id}`}
      onClick={() => void evaluation.selectCase(item.id)}><span>{item.root_id}</span>
      <ChevronLeft size={15} aria-hidden="true" /></button></td>
    <td><span className={`case-status ${item.status}`}>
      {item.status === "completed" && <CheckCircle2 size={14} />}
      {item.status === "failed" && <AlertTriangle size={14} />}
      {STATUS[item.status] ?? item.status}</span></td>
    <td>{duration(item.duration_seconds)}</td>
    <td>{item.rating ? `${item.rating}/5` : "—"}</td>
  </tr>;
}

function CaseDetail({ evaluation }: { evaluation: EvaluationController }) {
  const detail = evaluation.selectedCase;
  if (!detail) return <section className="evaluation-detail empty">
    <span className="evaluation-empty-icon"><Search size={25} /></span>
    <h2>בחרו תוצאה לבדיקה</h2>
    <p>הסיכום המלא, סיבת הכשל והדירוג יופיעו כאן.</p></section>;
  return <section className="evaluation-detail">
    <header><div><span>root_id</span><strong dir="ltr" title={detail.root_id}>
      {detail.root_id}</strong></div>
      <span className={`case-status ${detail.status}`}>
        {STATUS[detail.status] ?? detail.status}</span></header>
    <div className="evaluation-detail-scroll">
      {detail.run_id ? <EvaluationSummary detail={detail} /> :
        <p className="evaluation-pending-copy">הסיכום עדיין לא התחיל.</p>}
      {detail.error && <div className="evaluation-failure" role="alert">
        <AlertTriangle size={18} /><div><strong>סיבת הכשל</strong>
          <p>{detail.error}</p>{detail.run_id && <small dir="ltr">
            run {detail.run_id}</small>}</div></div>}
      {["completed", "partial", "failed"].includes(detail.status) &&
        <Review key={detail.id} detail={detail} evaluation={evaluation} />}
    </div>
  </section>;
}

function EvaluationSummary({ detail }: { detail: EvaluationCaseDetail }) {
  const run = toRun(detail);
  return run ? <article className="evaluation-summary"><SummaryContent run={run} />
    </article> : null;
}

function Review({
  detail, evaluation,
}: {
  detail: EvaluationCaseDetail;
  evaluation: EvaluationController;
}) {
  const [rating, setRating] = useState<1 | 2 | 3 | 4 | 5 | null>(detail.rating);
  const [comment, setComment] = useState(detail.comment ?? "");
  return <section className="evaluation-review" aria-labelledby="review-title">
    <header><h3 id="review-title">בדיקה ידנית</h3>
      <span>{rating ? `${rating}/5` : "טרם דורג"}</span></header>
    <div className="evaluation-stars" role="radiogroup" aria-label="דירוג הסיכום">
      {([1, 2, 3, 4, 5] as const).map((value) => <button type="button"
        role="radio" aria-checked={rating === value} key={value}
        aria-label={`${value} מתוך 5`} className={rating && value <= rating ? "active" : ""}
        onClick={() => setRating(value)}><Star size={20}
          fill={rating && value <= rating ? "currentColor" : "none"} /></button>)}
    </div>
    <label><span>הערה</span><textarea rows={4} maxLength={5000} value={comment}
      onChange={(event) => setComment(event.target.value)}
      placeholder="מה עבד ומה צריך לשפר?" /></label>
    <button className="primary-button" type="button" disabled={evaluation.busy}
      onClick={() => void evaluation.saveReview(rating, comment)}>
      שמירת בדיקה</button>
  </section>;
}

function toRun(detail: EvaluationCaseDetail): SummaryRun | null {
  if (!detail.run_id || !detail.run_status) return null;
  return {
    id: detail.run_id, conversation_id: detail.conversation_id ?? "",
    kind: "full", question: detail.question ?? "",
    skill_keys: detail.skill_keys ?? [], status: detail.run_status,
    progress: detail.progress ?? { completed: 0, total: 0, sections: [] },
    result: detail.result, error: detail.error,
    created_at: detail.run_created_at ?? "",
  };
}

function duration(value: number | null) {
  if (value == null) return "—";
  return value < 60 ? `${Math.round(value)} שנ׳` : `${Math.floor(value / 60)}:${String(
    Math.round(value % 60),
  ).padStart(2, "0")} דק׳`;
}

function safeName(value: string) {
  return value.replace(/[\\/:*?"<>|]+/g, "-").slice(0, 80) || "evaluation";
}
