"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, BookOpen, LoaderCircle, RefreshCw, Workflow, Wrench, X,
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
    <div className="modal-backdrop studio-backdrop" role="presentation">
      <section className="modal studio-modal" role="dialog" aria-modal="true"
        aria-labelledby="studio-title">
        <StudioHeader studio={studio} onClose={onClose} />
        <StudioContent studio={studio} />
      </section>
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
      .then(() => { setAuthenticated(true); void refresh(); })
      .catch(() => setAuthenticated(false));
  }, [refresh]);
  const counts = useMemo(() => ({
    packages: packages.length, workflows: workflows.length,
    content: content.length, review: review.length,
  }), [packages, workflows, content, review]);
  const login = () => { setAuthenticated(true); void refresh(); };
  const logout = () => { void api.logout(); setAuthenticated(false); };
  return {
    authenticated, tab, setTab, packages, workflows, content, review, error,
    refresh, counts, login, logout,
  };
}

type Studio = ReturnType<typeof useStudio>;

function StudioHeader({
  studio, onClose,
}: {
  studio: Studio;
  onClose: () => void;
}) {
  return (
    <header className="modal-header studio-header">
      <span className="modal-icon"><Workflow size={20} /></span>
      <div><h2 id="studio-title">מרכז ניהול</h2>
        <p>מקורות מידע, תהליכי סיכום, Skills ובקרת איכות.</p>
      </div>
      {studio.authenticated &&
        <button type="button" onClick={studio.logout}
          aria-label="יציאה מהסטודיו"><LogOut size={19} /></button>}
      <button type="button" onClick={onClose} aria-label="סגירה"><X /></button>
    </header>
  );
}

function StudioContent({ studio }: { studio: Studio }) {
  if (studio.authenticated === null) {
    return <p className="loading-line">
      <LoaderCircle className="spin" /> בודק הרשאה…
    </p>;
  }
  if (!studio.authenticated) return <StudioLogin onLogin={studio.login} />;
  return (
    <>
      <StudioTabs studio={studio} />
      {studio.error &&
        <p className="studio-global-error" role="alert">{studio.error}</p>}
      <StudioBody studio={studio} />
    </>
  );
}

function StudioTabs({ studio }: { studio: Studio }) {
  const tabs = [
    ["packages", "מקורות מידע", Wrench],
    ["workflows", "תהליכי סיכום", Workflow],
    ["content", "Skills והנחיות", BookOpen],
    ["review", "תור שיפור", AlertTriangle],
  ] as const;
  return (
    <nav className="studio-tabs" aria-label="אזורי Agent Studio">
      {tabs.map(([key, label, Icon]) =>
        <button type="button" key={key}
          className={studio.tab === key ? "active" : ""}
          onClick={() => studio.setTab(key)}>
          <Icon size={17} /> {label}<span>{studio.counts[key]}</span>
        </button>)}
      <button type="button" className="refresh-button"
        onClick={() => void studio.refresh()} aria-label="רענון נתונים">
        <RefreshCw size={17} />
      </button>
    </nav>
  );
}

function StudioBody({ studio }: { studio: Studio }) {
  return (
    <div className="studio-body">
      {studio.tab === "packages" &&
        <PackageCatalog items={studio.packages} onRefresh={studio.refresh} />}
      {studio.tab === "workflows" &&
        <WorkflowEditor packages={studio.packages} workflows={studio.workflows}
          onRefresh={studio.refresh} />}
      {studio.tab === "content" &&
        <ContentStudio items={studio.content} onRefresh={studio.refresh} />}
      {studio.tab === "review" && <ReviewQueue items={studio.review} />}
    </div>
  );
}
