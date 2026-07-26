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
  const [selectedSkillKeys, setSelectedSkillKeys] = useState<string[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
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
  useRunPolling(run, setRun, setError, loadHistory);

  const startNew = () => {
    setConversation(null); setRun(null); setRootId(""); setMessage("");
    setError(""); setNotice(""); setSelectedSkillKeys([]);
    setGeoMode("none"); setGeometry(null); setSidebarOpen(false);
  };

  const selectConversation = async (id: string) => {
    setError("");
    try {
      const selected = await api.conversation(id);
      setConversation(selected); setRootId(selected.root_id);
      const lastRun = selected.runs?.at(-1) ?? null;
      setRun(lastRun); setSelectedSkillKeys(lastRun?.skill_keys ?? []);
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
      const detected = detectIdentifier(rootId, message, conversation);
      if (detected) {
        setRootId(detected); setNotice(identifierNotice(detected));
        return;
      }
      const next = await submitRequest(
        conversation, rootId, message, selectedSkillKeys, geometry
      );
      setConversation(next.conversation); setRun(next.run);
      setMessage(""); loadHistory();
    } catch (reason) {
      setError(errorMessage(reason, "הפעולה נכשלה"));
    } finally {
      setSubmitting(false);
    }
  };

  const toggleSkill = (key: string) => {
    setError("");
    setSelectedSkillKeys((current) => toggleKey(current, key, setError));
  };

  return {
    rootId, setRootId, message, setMessage, geoMode, setGeoMode,
    geometry, setGeometry, conversations, skills, selectedSkillKeys,
    conversation, run, error, submitting, sidebarOpen, setSidebarOpen,
    settingsOpen, setSettingsOpen, studioOpen, setStudioOpen, dark, setDark,
    notice, startNew, selectConversation, submit, toggleSkill,
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
  setError: Setter<string>,
  loadHistory: () => void,
) {
  useEffect(() => {
    if (!run || !isActive(run)) return;
    const timer = window.setInterval(() => {
      api.run(run.id).then((next) => {
        setRun(next);
        if (!isActive(next)) loadHistory();
      }).catch((reason) => setError(reason.message));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [run, setRun, setError, loadHistory]);
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

function toggleKey(current: string[], key: string, setError: Setter<string>) {
  if (current.includes(key)) return current.filter((item) => item !== key);
  if (current.length < 3) return [...current, key];
  setError("אפשר לבחור עד 3 Skills בכל סיכום");
  return current;
}

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
