"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type {
  EvaluationBatch, EvaluationCaseDetail, EvaluationCasePage,
} from "@/types";

const PAGE_SIZE = 50;
const ACTIVE = new Set(["running", "pausing", "paused", "stopping"]);

export function useEvaluation() {
  const [batches, setBatches] = useState<EvaluationBatch[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [batch, setBatch] = useState<EvaluationBatch | null>(null);
  const [cases, setCases] = useState<EvaluationCasePage>({
    items: [], total: 0, offset: 0, limit: PAGE_SIZE,
  });
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [selectedCase, setSelectedCase] = useState<EvaluationCaseDetail | null>(null);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadBatches = useCallback(async () => {
    const items = await api.evaluations();
    setBatches(items);
    setSelectedId((current) => current ?? items[0]?.id ?? null);
    return items;
  }, []);

  const loadSelected = useCallback(async () => {
    if (!selectedId) {
      setBatch(null); setCases({ items: [], total: 0, offset: 0, limit: PAGE_SIZE });
      return;
    }
    const offset = page * PAGE_SIZE;
    const [nextBatch, nextCases] = await Promise.all([
      api.evaluation(selectedId),
      api.evaluationCases(selectedId, offset, PAGE_SIZE, status, search),
    ]);
    setBatch(nextBatch); setCases(nextCases);
    if (selectedCaseId) {
      const detail = await api.evaluationCase(selectedId, selectedCaseId);
      setSelectedCase(detail);
    }
  }, [selectedId, page, status, search, selectedCaseId]);

  const refresh = useCallback(async (showLoader = false) => {
    if (showLoader) setLoading(true);
    try {
      setError("");
      await Promise.all([loadBatches(), loadSelected()]);
    } catch (reason) {
      setError(message(reason, "טעינת ה-Evaluation נכשלה"));
    } finally {
      if (showLoader) setLoading(false);
    }
  }, [loadBatches, loadSelected]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadBatches()
        .catch((reason) => setError(message(reason, "טעינת ה-Evaluation נכשלה")))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadBatches]);
  useEffect(() => {
    if (!selectedId) return;
    const timer = window.setTimeout(() => {
      loadSelected().catch((reason) =>
        setError(message(reason, "טעינת ה-Evaluation נכשלה")));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [selectedId, loadSelected]);
  useEffect(() => {
    if (!batch || !ACTIVE.has(batch.status)) return;
    const timer = window.setInterval(() => void refresh(), 1500);
    return () => window.clearInterval(timer);
  }, [batch, refresh]);

  const selectBatch = (id: string | null) => {
    setSelectedId(id); setBatch(null); setSelectedCaseId(null);
    setSelectedCase(null); setStatus(""); setSearch(""); setPage(0);
  };

  const selectCase = async (caseId: string) => {
    if (!selectedId) return;
    setSelectedCaseId(caseId); setError("");
    try {
      setSelectedCase(await api.evaluationCase(selectedId, caseId));
    } catch (reason) {
      setError(message(reason, "טעינת הסיכום נכשלה"));
    }
  };

  const created = async (createdBatch: EvaluationBatch) => {
    await loadBatches(); selectBatch(createdBatch.id);
  };

  const action = async (
    call: () => Promise<EvaluationBatch>, fallback: string,
  ) => {
    setBusy(true); setError("");
    try {
      const changed = await call();
      setBatch(changed); await loadBatches(); await loadSelected();
    } catch (reason) {
      setError(message(reason, fallback));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!batch) return;
    const completed = batch.completed + batch.partial + batch.failed;
    if (!window.confirm(
      `למחוק לצמיתות את “${batch.label}”?\n` +
      `${completed} סיכומים, הראיות והציונים שלהם יימחקו ללא אפשרות שחזור.`,
    )) return;
    setBusy(true); setError("");
    try {
      await api.deleteEvaluation(batch.id);
      const remaining = await loadBatches();
      selectBatch(remaining[0]?.id ?? null);
    } catch (reason) {
      setError(message(reason, "מחיקת הסשן נכשלה"));
    } finally {
      setBusy(false);
    }
  };

  const saveReview = async (
    rating: 1 | 2 | 3 | 4 | 5 | null, comment: string,
  ) => {
    if (!batch || !selectedCase) return;
    setBusy(true); setError("");
    try {
      const updated = await api.reviewEvaluationCase(
        batch.id, selectedCase.id, rating, comment,
      );
      setSelectedCase(updated); await loadSelected(); await loadBatches();
    } catch (reason) {
      setError(message(reason, "שמירת הבדיקה נכשלה"));
    } finally {
      setBusy(false);
    }
  };

  const retryFailed = async () => {
    if (!batch) return;
    setBusy(true); setError("");
    try {
      const retried = await api.retryFailedEvaluation(batch.id);
      await created(retried);
    } catch (reason) {
      setError(message(reason, "הרצת הנכשלים נכשלה"));
    } finally {
      setBusy(false);
    }
  };

  const activeBatch = useMemo(
    () => batches.find((item) => ACTIVE.has(item.status)) ?? null,
    [batches],
  );

  return {
    batches, selectedId, batch, cases, selectedCase, selectedCaseId,
    status, search, page, loading, busy, error, activeBatch,
    reportError: (value: string) => setError(value),
    setStatus: (value: string) => { setStatus(value); setPage(0); },
    setSearch: (value: string) => { setSearch(value); setPage(0); },
    setPage, selectBatch, selectCase, created, refresh, action, remove,
    saveReview, retryFailed,
  };
}

export type EvaluationController = ReturnType<typeof useEvaluation>;

function message(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
