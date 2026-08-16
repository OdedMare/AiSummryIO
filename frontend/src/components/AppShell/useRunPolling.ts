import type { Dispatch, SetStateAction } from "react";
import { useEffect } from "react";
import { api } from "@/services/api";
import type { SummaryRun } from "@/types";

type Setter<T> = Dispatch<SetStateAction<T>>;

export const isActive = (run: SummaryRun | null) =>
  run?.status === "queued" || run?.status === "running";

export function useRunPolling(
  run: SummaryRun | null,
  setRun: Setter<SummaryRun | null>,
  setRuns: Setter<SummaryRun[]>,
  setError: Setter<string>,
  loadHistory: () => void,
) {
  const runId = run?.id;
  const active = isActive(run);
  useEffect(() => {
    if (!runId || !active) return;
    const startedAt = Date.now();
    let timer: number | undefined;
    let stopped = false;
    let warned = false;
    console.debug(`[poll] watching run ${runId}`);

    const poll = () => {
      api.run(runId).then((next) => {
        if (stopped) return;
        const age = (Date.now() - startedAt) / 1000;
        const done = next.progress?.completed ?? 0;
        const total = next.progress?.total ?? 0;
        console.debug(
          `[poll] run ${next.id} status=${next.status} `
          + `progress=${done}/${total} age=${age.toFixed(0)}s`,
        );
        if (isActive(next) && age > 180 && !warned) {
          warned = true;
          console.warn(
            `[poll] run ${next.id} has been ${next.status} for `
            + `${age.toFixed(0)}s with no completion — check the backend `
            + "console for an external-call timeout.",
          );
        }
        setRun(next);
        setRuns((thread) => thread.map(
          (item) => item.id === next.id ? next : item,
        ));
        if (!isActive(next)) {
          console.debug(
            `[poll] run ${next.id} finished as ${next.status} `
            + `after ${age.toFixed(1)}s`,
          );
          loadHistory();
          return;
        }
        timer = window.setTimeout(poll, 1500);
      }).catch((reason) => {
        if (stopped) return;
        console.error(`[poll] run ${runId} poll failed`, reason);
        setError(reason.message);
        timer = window.setTimeout(poll, 1500);
      });
    };

    timer = window.setTimeout(poll, 1500);
    return () => {
      stopped = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [runId, active, setRun, setRuns, setError, loadHistory]);
}
