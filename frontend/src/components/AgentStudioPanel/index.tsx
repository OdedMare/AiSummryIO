"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, ArrowRight, BookOpen, LoaderCircle, RefreshCw, Workflow,
  Wrench,
} from "lucide-react";
import { api } from "@/services/api";
import type {
  AgentContent, PackageVersion, WorkflowVersion,
} from "@/types";
import ContentStudio from "./ContentStudio";
import PackageCatalog from "./PackageCatalog";
import { ReviewQueue } from "./StudioCommon";
import WorkflowEditor from "./WorkflowEditor";

type Tab = "packages" | "workflows" | "content" | "review";

export default function AgentStudioPanel({ onClose }: { onClose: () => void }) {
  const studio = useStudio();
  return (
    <div className="studio-page">
      <StudioHeader onClose={onClose} studio={studio} />
      <StudioContent studio={studio} />
    </div>
  );
}

function useStudio() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [tab, setTab] = useState<Tab>("workflows");
  const [packages, setPackages] = useState<PackageVersion[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowVersion[]>([]);
  const [content, setContent] = useState<AgentContent[]>([]);
  const [review, setReview] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    setError("");
    try {
      const values = await Promise.all([
        api.packages(), api.workflows(), api.content(), api.reviewQueue(),
      ]);
      setPackages(values[0]); setWorkflows(values[1]);
      setContent(values[2]); setReview(values[3]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "טעינת הסטודיו נכשלה");
    }
  }, []);
  useEffect(() => {
    api.adminSession()
      .then(() => { setAuthorized(true); void refresh(); })
      .catch(() => setAuthorized(false));
  }, [refresh]);
  const counts = useMemo(() => ({
    packages: packages.length, workflows: workflows.length,
    content: content.length, review: review.length,
  }), [packages, workflows, content, review]);
  return {
    authorized, tab, setTab, packages, workflows, content, review, error,
    refresh, counts,
  };
}

type Studio = ReturnType<typeof useStudio>;

function StudioHeader({
  onClose, studio,
}: {
  onClose: () => void;
  studio: Studio;
}) {
  return (
    <header className="studio-page-header">
      <button type="button" className="studio-back" onClick={onClose}>
        <ArrowRight size={17} aria-hidden="true" /> חזרה לשיחה
      </button>
      <span className="modal-icon"><Workflow size={20} /></span>
      <div><span className="studio-kicker">SumOrAI Workspace</span>
        <h2 id="studio-title" dir="ltr">SumOrAI Agent Studio</h2>
      </div>
      {studio.authorized &&
        <button type="button" className="studio-refresh"
          onClick={() => void studio.refresh()}>
          <RefreshCw size={16} aria-hidden="true" /> רענון
        </button>}
    </header>
  );
}

function StudioContent({ studio }: { studio: Studio }) {
  if (studio.authorized === null) {
    return <p className="loading-line">
      <LoaderCircle className="spin" /> בודק הרשאה…
    </p>;
  }
  if (!studio.authorized) {
    return <p className="studio-global-error" role="alert">
      <AlertTriangle size={18} /> אין הרשאת FDE. יש להגדיר טוקן API תקין בשרת.
    </p>;
  }
  return (
    <div className="studio-page-body">
      <StudioNav studio={studio} />
      <main className="studio-main">
        {studio.error &&
          <p className="studio-global-error" role="alert">{studio.error}</p>}
        <StudioBody studio={studio} />
      </main>
    </div>
  );
}

const TABS = [
  ["packages", "מקורות מידע", "חבילות FLAPI", Wrench],
  ["workflows", "תהליכי סיכום", "Workflows", Workflow],
  ["content", "Skills והנחיות", "ניסוח וסיכום", BookOpen],
  ["review", "תור שיפור", "מה נכשל", AlertTriangle],
] as const;

function StudioNav({ studio }: { studio: Studio }) {
  return (
    <nav className="studio-nav" aria-label="אזורי Agent Studio">
      {TABS.map(([key, label, hint, Icon]) =>
        <button type="button" key={key}
          className={studio.tab === key ? "active" : ""}
          aria-current={studio.tab === key ? "page" : undefined}
          onClick={() => studio.setTab(key)}>
          <Icon size={18} aria-hidden="true" />
          <span className="studio-nav-label">{label}<small>{hint}</small></span>
          <span className="studio-nav-count">{studio.counts[key]}</span>
        </button>)}
    </nav>
  );
}

function StudioBody({ studio }: { studio: Studio }) {
  if (studio.tab === "packages") {
    return <PackageCatalog items={studio.packages} onRefresh={studio.refresh} />;
  }
  if (studio.tab === "workflows") {
    return <WorkflowEditor packages={studio.packages}
      workflows={studio.workflows} onRefresh={studio.refresh} />;
  }
  if (studio.tab === "content") {
    return <ContentStudio items={studio.content} onRefresh={studio.refresh} />;
  }
  return <ReviewQueue items={studio.review} />;
}
