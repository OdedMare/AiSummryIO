import { useState } from "react";
import type { PlanChatMessage, PlanQuestion } from "@/types";

export interface PlanTurn<TDraft> {
  reply: string;
  question: PlanQuestion | null;
  resolved: string[];
  open_points: string[];
  awaiting_confirmation: boolean;
  ready: boolean;
  draft: TDraft;
}

export interface PlanChatState<TDraft> {
  messages: PlanChatMessage[];
  draft: TDraft | null;
  question: PlanQuestion | null;
  resolved: string[];
  openPoints: string[];
  awaitingConfirmation: boolean;
  pending: boolean;
  error: string;
  send: (text: string) => Promise<void>;
  confirm: () => void;
  reset: () => void;
}

export function usePlanChat<TDraft>(
  onTurn: (
    messages: PlanChatMessage[],
    draft: TDraft | null,
  ) => Promise<PlanTurn<TDraft>>,
  onReady?: (draft: TDraft) => void,
): PlanChatState<TDraft> {
  const [messages, setMessages] = useState<PlanChatMessage[]>([]);
  const [draft, setDraft] = useState<TDraft | null>(null);
  const [question, setQuestion] = useState<PlanQuestion | null>(null);
  const [resolved, setResolved] = useState<string[]>([]);
  const [openPoints, setOpenPoints] = useState<string[]>([]);
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const send = async (text: string) => {
    const said = text.trim();
    if (!said || pending) return;
    const history: PlanChatMessage[] = [
      ...messages,
      { role: "fde", text: said },
    ];
    setMessages(history);
    setPending(true);
    setError("");
    setQuestion(null);
    try {
      const turn = await onTurn(history, draft);
      setMessages([...history, { role: "agent", text: turn.reply }]);
      setDraft(turn.draft);
      setQuestion(turn.question);
      setResolved(turn.resolved);
      setOpenPoints(turn.open_points);
      setAwaitingConfirmation(turn.awaiting_confirmation);
      if (turn.ready) onReady?.(turn.draft);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "השיחה נכשלה");
    } finally {
      setPending(false);
    }
  };

  const confirm = () => {
    if (!draft || !awaitingConfirmation || pending) return;
    setMessages([
      ...messages,
      { role: "fde", text: "מאשר, הגענו להסכמה." },
    ]);
    setAwaitingConfirmation(false);
    onReady?.(draft);
  };

  const reset = () => {
    setMessages([]);
    setDraft(null);
    setQuestion(null);
    setResolved([]);
    setOpenPoints([]);
    setAwaitingConfirmation(false);
    setError("");
  };

  return {
    messages,
    draft,
    question,
    resolved,
    openPoints,
    awaitingConfirmation,
    pending,
    error,
    send,
    confirm,
    reset,
  };
}
