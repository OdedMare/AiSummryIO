"use client";

import {
  Dispatch, FormEvent, SetStateAction, useCallback, useEffect, useState,
} from "react";
import { api } from "@/services/api";
import type { Conversation, SummaryRun, SummarySkill } from "@/types";
import { toMultiPolygon } from "@/types/geo";
import type { GeographyMode, GeoJSONPolygon } from "@/types/geo";

export const isActive = (run: SummaryRun | null) =>
  run?.status === "queued" || run?.status === "running";

type Setter<T> = Dispatch<SetStateAction<T>>;

export function useAppShell() {
  const [rootId, setRootId] = useState("");
  const [message, setMessage] = useState("");
  const [geoMode, setGeoMode] = useState<GeographyMode>("none");
  const [geometry, setGeometry] = useState<GeoJSONPolygon | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [skills, setSkills] = useState<SummarySkill[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  /* The whole thread, oldest first. `run` is the turn still being polled, so
     the transcript and the poll loop do not fight over one piece of state. */
  const [runs, setRuns] = useState<SummaryRun[]>([]);
  const [run, setRun] = useState<SummaryRun | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [studioOpen, setStudioOpen] = useState(false);
  const [dark, setDark] = useState(true);
  const [notice, setNotice] = useState("");

  const loadHistory = useCallback(() => {
    api.conversations().then(setConversations).catch(() => undefined);
  }, []);

  useInitialData(loadHistory, setDark, setSkills);
  useTheme(dark);
  useRunPolling(run, setRun, setRuns, setError, loadHistory);

  const startNew = () => {
    setConversation(null); setRun(null); setRuns([]); setRootId("");
    setMessage(""); setError(""); setNotice("");
    setGeoMode("none"); setGeometry(null); setSidebarOpen(false);
  };

  const selectConversation = async (id: string) => {
    setError("");
    try {
      const selected = await api.conversation(id);
      setConversation(selected); setRootId(selected.root_id);
      const thread = selected.runs ?? [];
      setRuns(thread);
      // Only the last turn can still be running, so it is the one polled.
      setRun(thread.at(-1) ?? null);
      setSidebarOpen(false);
    } catch (reason) {
      setError(errorMessage(reason, "לא ניתן לטעון שיחה"));
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting || isActive(run)) return;
    setSubmitting(true); setError(""); setNotice("");
    try {
      const parsed = parseCommands(message, skills);
      const detected = detectIdentifier(rootId, parsed.text, conversation);
      if (detected) {
        setRootId(detected); setNotice(identifierNotice(detected));
        return;
      }
      if (parsed.unknown.length) throw new Error(unknownNotice(parsed.unknown));
      const next = await submitRequest(
        conversation, rootId, parsed.text, parsed.keys, geometry
      );
      setConversation(next.conversation);
      setRun(next.run);
      // A new conversation starts the thread; a follow-up extends it.
      setRuns((thread) => conversation ? [...thread, next.run] : [next.run]);
      setMessage(""); loadHistory();
    } catch (reason) {
      setError(errorMessage(reason, "הפעולה נכשלה"));
    } finally {
      setSubmitting(false);
    }
  };

  return {
    rootId, setRootId, message, setMessage, geoMode, setGeoMode,
    geometry, setGeometry, conversations, skills,
    conversation, run, runs, error, submitting, sidebarOpen, setSidebarOpen,
    settingsOpen, setSettingsOpen, studioOpen, setStudioOpen, dark, setDark,
    notice, startNew, selectConversation, submit,
  };
}

export type AppShellController = ReturnType<typeof useAppShell>;

function useInitialData(
  loadHistory: () => void,
  setDark: Setter<boolean>,
  setSkills: Setter<SummarySkill[]>,
) {
  useEffect(() => {
    const saved = window.localStorage.getItem("aisummry-theme");
    const dark = saved ? saved === "dark" :
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.setTimeout(() => setDark(dark), 0);
    loadHistory();
    api.skills().then(setSkills).catch(() => undefined);
  }, [loadHistory, setDark, setSkills]);
}

function useTheme(dark: boolean) {
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.localStorage.setItem("aisummry-theme", dark ? "dark" : "light");
  }, [dark]);
}

function useRunPolling(
  run: SummaryRun | null,
  setRun: Setter<SummaryRun | null>,
  setRuns: Setter<SummaryRun[]>,
  setError: Setter<string>,
  loadHistory: () => void,
) {
  useEffect(() => {
    if (!run || !isActive(run)) return;
    const startedAt = Date.now();
    console.debug(`[poll] watching run ${run.id} (status=${run.status})`);
    const timer = window.setInterval(() => {
      api.run(run.id).then((next) => {
        const age = (Date.now() - startedAt) / 1000;
        const done = next.progress?.completed ?? 0;
        const total = next.progress?.total ?? 0;
        // The whole symptom of a stuck run is that this line repeats with
        // the same numbers, so age and progress are printed every tick.
        console.debug(
          `[poll] run ${next.id} status=${next.status} ` +
          `progress=${done}/${total} age=${age.toFixed(0)}s`,
        );
        if (isActive(next) && age > 180) {
          console.warn(
            `[poll] run ${next.id} has been ${next.status} for ${age.toFixed(0)}s ` +
            "with no completion — check the backend console for a FLAPI timeout.",
          );
        }
        setRun(next);
        // Keyed by id rather than by position: the thread is what the
        // transcript renders, so a progress tick has to reach it too.
        setRuns((thread) => thread.map(
          (item) => item.id === next.id ? next : item,
        ));
        if (!isActive(next)) {
          console.debug(
            `[poll] run ${next.id} finished as ${next.status} ` +
            `after ${age.toFixed(1)}s`,
          );
          loadHistory();
        }
      }).catch((reason) => {
        console.error(`[poll] run ${run.id} poll failed`, reason);
        setError(reason.message);
      });
    }, 1500);
    return () => window.clearInterval(timer);
  }, [run, setRun, setRuns, setError, loadHistory]);
}

function detectIdentifier(
  rootId: string, message: string, conversation: Conversation | null
) {
  if (conversation || rootId.trim()) return null;
  const match = message.match(
    /(?:^|\s)(?:id|מזהה)\s*[:#=-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{0,255})(?:\s|$)/i,
  );
  if (!match) throw new Error("יש להזין מזהה בשדה או לכתוב „מזהה: …”");
  return match[1];
}

function identifierNotice(identifier: string) {
  return `זיהינו את המזהה ${identifier}. בדקו אותו ולחצו שוב לאישור.`;
}

async function submitRequest(
  conversation: Conversation | null,
  rootId: string,
  message: string,
  skillKeys: string[],
  geometry: GeoJSONPolygon | null,
) {
  if (conversation) {
    if (!message.trim()) throw new Error("יש לכתוב שאלת המשך");
    const run = await api.followUp(conversation.id, message.trim(), skillKeys);
    return { conversation, run };
  }
  const created = await api.start(
    rootId.trim(), message.trim(), skillKeys,
    geometry ? toMultiPolygon(geometry) : null,
  );
  return created;
}

/** A `/` that starts a command: at the beginning or after whitespace. */
const COMMAND = /(^|\s)\/(\S[^\n]*)/;

const normalize = (value: string) =>
  value.trim().toLowerCase().replace(/[\s_-]+/g, " ");

/** Every spelling a Skill answers to. */
function aliases(skill: SummarySkill) {
  return [
    skill.name, skill.content_key, skill.content_key.replace(/^summary-/, ""),
  ].map(normalize);
}

/**
 * Pulls `/name` commands out of the message and maps them to Skill keys.
 * A command matches a Skill's Hebrew name or its `content_key`, with or
 * without the `summary-` prefix, so `/תקציר מנהלים` and `/executive` both work.
 * Names may contain spaces, so the longest run of words after the slash that
 * matches an alias wins; anything past it stays in the message text.
 */
export function parseCommands(message: string, skills: SummarySkill[]) {
  const keys: string[] = [];
  const unknown: string[] = [];
  let text = "";
  let rest = message;
  for (let found = COMMAND.exec(rest); found; found = COMMAND.exec(rest)) {
    const [whole, lead, tail] = found;
    text += rest.slice(0, found.index) + lead;
    const match = matchSkill(tail, skills);
    if (!match) {
      const name = firstWords(tail);
      const skip = consumed(tail, name.split(/\s+/).length);
      unknown.push(name);
      text += whole.slice(lead.length, whole.length - tail.length) + skip;
      rest = tail.slice(skip.length);
      continue;
    }
    if (!keys.includes(match.key)) keys.push(match.key);
    rest = tail.slice(match.length);
  }
  return { text: (text + rest).replace(/\s+/g, " ").trim(), keys, unknown };
}

/** Longest run of leading words in `rest` matching an alias, if any. */
function matchSkill(rest: string, skills: SummarySkill[]) {
  const all = skills.flatMap((skill) =>
    aliases(skill).map((alias) => ({ key: skill.content_key, alias })));
  const words = Math.max(...all.map((entry) => entry.alias.split(" ").length));
  for (let count = words; count > 0; count -= 1) {
    const prefix = consumed(rest, count);
    if (!prefix) continue;
    const wanted = normalize(prefix);
    const entry = all.find((item) => item.alias === wanted);
    if (entry) return { key: entry.key, length: prefix.length };
  }
  return null;
}

/** The first `count` whitespace-delimited words of `value`, verbatim. */
function consumed(value: string, count: number) {
  const match = value.match(new RegExp(`^(?:\\s*\\S+){1,${count}}`));
  return match ? match[0] : "";
}

const firstWords = (rest: string) =>
  rest.split(/\s\//)[0].trim().split(/\s+/).slice(0, 4).join(" ");

function unknownNotice(unknown: string[]) {
  return `לא מצאנו Skill בשם ${unknown.map((n) => `„${n}”`).join(", ")}. ` +
    "כתבו / כדי לראות את הרשימה.";
}

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
