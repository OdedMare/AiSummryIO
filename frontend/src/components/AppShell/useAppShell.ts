"use client";

import type { FormEvent } from "react";
import { useCallback, useState } from "react";
import { api } from "@/services/api";
import type {
  Conversation, SummaryAgent, SummaryRun, SummarySkill,
} from "@/types";
import type { GeographyMode, GeoJSONPolygon } from "@/types/geo";
import { toMultiPolygonParts } from "@/types/geo";
import {
  detectIdentifier,
  identifierNotice,
  parseCommands,
  unknownNotice,
} from "./commands";
import { useInitialData, useTheme } from "./useShellTheme";
import { isActive, useRunPolling } from "./useRunPolling";

export { parseCommands } from "./commands";
export { isActive } from "./useRunPolling";

export function useAppShell() {
  const [rootId, setRootId] = useState("");
  const [message, setMessage] = useState("");
  const [geoMode, setGeoMode] = useState<GeographyMode>("none");
  // Every part the user drew. They are sent as one MultiPolygon, so a scope
  // made of several disjoint areas is one request, not several.
  const [geometry, setGeometry] = useState<GeoJSONPolygon[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [skills, setSkills] = useState<SummarySkill[]>([]);
  const [agents, setAgents] = useState<SummaryAgent[]>([]);
  const [selectedAgentKeys, setSelectedAgentKeys] = useState<string[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [runs, setRuns] = useState<SummaryRun[]>([]);
  const [run, setRun] = useState<SummaryRun | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [studioOpen, setStudioOpen] = useState(false);
  const [evaluationOpen, setEvaluationOpen] = useState(false);
  const [dark, setDark] = useState(true);
  const [notice, setNotice] = useState("");

  const loadHistory = useCallback(() => {
    api.conversations().then(setConversations).catch(() => undefined);
  }, []);

  useInitialData(loadHistory, setDark, setSkills, setAgents);
  useTheme(dark);
  useRunPolling(run, setRun, setRuns, setError, loadHistory);

  const startNew = () => {
    setConversation(null);
    setRun(null);
    setRuns([]);
    setRootId("");
    setMessage("");
    setError("");
    setNotice("");
    setGeoMode("none");
    setGeometry([]);
    setSidebarOpen(false);
  };

  /** Appends a finished part; the draw tool stays armed for the next one. */
  const addGeometry = (part: GeoJSONPolygon) => {
    setGeometry((parts) => [...parts, part]);
  };
  const undoGeometry = () => setGeometry((parts) => parts.slice(0, -1));
  const clearGeometry = () => { setGeometry([]); setGeoMode("none"); };

  const endConversation = async () => {
    if (!conversation || submitting || isActive(run)) return;
    const confirmed = window.confirm(
      "לסיים את השיחה ולמחוק לצמיתות את הסיכומים והראיות שלה?",
    );
    if (!confirmed) return;
    setSubmitting(true);
    setError("");
    try {
      await api.deleteConversation(conversation.id);
      startNew();
      loadHistory();
    } catch (reason) {
      setError(errorMessage(reason, "לא ניתן למחוק את השיחה"));
    } finally {
      setSubmitting(false);
    }
  };

  const selectConversation = async (id: string) => {
    setError("");
    try {
      const selected = await api.conversation(id);
      const thread = selected.runs ?? [];
      setConversation(selected);
      setRootId(selected.root_id);
      setRuns(thread);
      setRun(thread.at(-1) ?? null);
      setSidebarOpen(false);
    } catch (reason) {
      setError(errorMessage(reason, "לא ניתן לטעון שיחה"));
    }
  };

  const send = async (text: string) => {
    if (submitting || isActive(run)) return;
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      const parsed = parseCommands(text, skills);
      const detected = detectIdentifier(
        rootId,
        parsed.text,
        conversation,
        !!geometry.length,
      );
      if (detected) {
        setRootId(detected);
        setNotice(identifierNotice(detected));
        return;
      }
      if (parsed.unknown.length) throw new Error(unknownNotice(parsed.unknown));
      const next = await submitRequest(
        conversation,
        rootId,
        parsed.text,
        parsed.keys,
        geometry,
        selectedAgentKeys,
      );
      setConversation(next.conversation);
      // A map request is sent without an identifier and comes back carrying
      // one: the drawn area as WKT. Adopting what the server stored keeps the
      // shell showing the identifier the run actually uses.
      setRootId(next.conversation.root_id);
      setRun(next.run);
      setRuns((thread) => conversation ? [...thread, next.run] : [next.run]);
      setMessage("");
      loadHistory();
    } catch (reason) {
      setError(errorMessage(reason, "הפעולה נכשלה"));
    } finally {
      setSubmitting(false);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await send(message);
  };
  const ask = (question: string) => { void send(question); };

  return {
    rootId,
    setRootId,
    message,
    setMessage,
    geoMode,
    setGeoMode,
    geometry,
    setGeometry,
    addGeometry,
    undoGeometry,
    clearGeometry,
    conversations,
    skills,
    agents,
    selectedAgentKeys,
    toggleAgent: (key: string) => setSelectedAgentKeys((current) =>
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key]),
    conversation,
    run,
    runs,
    error,
    submitting,
    sidebarOpen,
    setSidebarOpen,
    settingsOpen,
    setSettingsOpen,
    studioOpen,
    setStudioOpen,
    evaluationOpen,
    setEvaluationOpen,
    dark,
    setDark,
    notice,
    startNew,
    endConversation,
    selectConversation,
    submit,
    ask,
  };
}

export type AppShellController = ReturnType<typeof useAppShell>;

async function submitRequest(
  conversation: Conversation | null,
  rootId: string,
  message: string,
  skillKeys: string[],
  geometry: GeoJSONPolygon[],
  agentKeys: string[],
) {
  if (conversation) {
    if (!message.trim()) throw new Error("יש לכתוב שאלת המשך");
    const run = await api.followUp(
      conversation.id, message.trim(), skillKeys, agentKeys,
    );
    return { conversation, run };
  }
  return api.start(
    rootId.trim(),
    message.trim(),
    skillKeys,
    toMultiPolygonParts(geometry),
    agentKeys,
  );
}

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
