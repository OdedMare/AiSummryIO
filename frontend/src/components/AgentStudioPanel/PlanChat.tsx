"use client";

import { useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { LoaderCircle, MessagesSquare, Send } from "lucide-react";

import type { PlanChatMessage } from "@/types";

/** One planning turn as the chat needs it, whatever kind of draft it carries. */
export interface PlanTurn<TDraft> {
  reply: string;
  questions: string[];
  ready: boolean;
  draft: TDraft;
}

export interface PlanChatState<TDraft> {
  messages: PlanChatMessage[];
  draft: TDraft | null;
  ready: boolean;
  questions: string[];
  pending: boolean;
  error: string;
  send: (text: string) => Promise<void>;
  reset: () => void;
}

/**
 * Drives a stateless planning conversation.
 *
 * The whole history is replayed to the server each turn, so this hook holds
 * the only copy of it. `onTurn` is what makes the hook reusable: it sends the
 * history and returns the next turn, leaving the endpoint to the caller.
 */
export function usePlanChat<TDraft>(
  onTurn: (
    messages: PlanChatMessage[], draft: TDraft | null,
  ) => Promise<PlanTurn<TDraft>>,
  onReady?: (draft: TDraft) => void,
): PlanChatState<TDraft> {
  const [messages, setMessages] = useState<PlanChatMessage[]>([]);
  const [draft, setDraft] = useState<TDraft | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const send = async (text: string) => {
    const said = text.trim();
    if (!said || pending) return;
    const history: PlanChatMessage[] = [...messages, { role: "fde", text: said }];
    setMessages(history); setPending(true); setError(""); setQuestions([]);
    try {
      const turn = await onTurn(history, draft);
      setMessages([...history, { role: "agent", text: turn.reply }]);
      setDraft(turn.draft); setQuestions(turn.questions); setReady(turn.ready);
      if (turn.ready && onReady) onReady(turn.draft);
    } catch (reason) {
      // The FDE's own message stays in the thread so it is not retyped.
      setError(reason instanceof Error ? reason.message : "השיחה נכשלה");
    } finally {
      setPending(false);
    }
  };

  const reset = () => {
    setMessages([]); setDraft(null); setQuestions([]);
    setReady(false); setError("");
  };

  return {
    messages, draft, ready, questions, pending, error, send, reset,
  };
}

export function PlanChat<TDraft>({
  chat, title, hint, children,
}: {
  chat: PlanChatState<TDraft>;
  title: string;
  hint: string;
  /** Draft preview rendered under the thread once there is something to show. */
  children?: React.ReactNode;
}) {
  const [text, setText] = useState("");
  const threadRef = useRef<HTMLDivElement>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const said = text;
    setText("");
    void chat.send(said);
  };
  // Enter sends, Shift+Enter breaks the line — as in the main composer.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const said = text;
      setText("");
      void chat.send(said);
    }
  };

  return (
    <section className="plan-chat" aria-labelledby="plan-chat-title">
      <header>
        <MessagesSquare size={17} aria-hidden="true" />
        <div>
          <h3 id="plan-chat-title">{title}</h3>
          <p>{hint}</p>
        </div>
        {!!chat.messages.length &&
          <button type="button" className="plan-chat-reset"
            onClick={chat.reset} disabled={chat.pending}>
            שיחה חדשה
          </button>}
      </header>

      <div className="plan-chat-thread" ref={threadRef} aria-live="polite">
        {chat.messages.map((message, index) => (
          <p key={index}
            className={`plan-chat-message ${message.role}`}>
            <span className="plan-chat-role">
              {message.role === "fde" ? "אני" : "הסוכן"}
            </span>
            {message.text}
          </p>
        ))}
        {chat.pending &&
          <p className="plan-chat-message agent pending">
            <LoaderCircle className="spin" size={15} aria-hidden="true" />
            הסוכן חושב…
          </p>}
        {!chat.messages.length && !chat.pending &&
          <p className="panel-empty">{hint}</p>}
      </div>

      {!!chat.questions.length &&
        <ul className="plan-chat-questions">
          {chat.questions.map((question, index) =>
            <li key={index}>
              <button type="button" onClick={() => setText(question)}>
                {question}
              </button>
            </li>)}
        </ul>}

      {chat.error &&
        <p className="panel-error" role="alert">{chat.error}</p>}

      {children}

      <form className="plan-chat-composer" onSubmit={submit}>
        <textarea id="plan-chat-input" rows={2} value={text}
          aria-label="הודעה לסוכן" placeholder="ספרו על הנתונים שלכם…"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown} disabled={chat.pending} />
        <button type="submit" disabled={chat.pending || !text.trim()}
          aria-label="שליחה לסוכן">
          {chat.pending
            ? <LoaderCircle className="spin" size={17} aria-hidden="true" />
            : <Send size={17} aria-hidden="true" />}
        </button>
      </form>
    </section>
  );
}
