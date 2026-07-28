"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { FormEvent, KeyboardEvent, ReactNode } from "react";
import {
  CheckCircle2, CircleDot, LoaderCircle, MessagesSquare, Send, Sparkles,
  ThumbsUp, X,
} from "lucide-react";

import type { PlanChatMessage, PlanQuestion } from "@/types";

/** One interview turn as the chat needs it, whatever draft it carries. */
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
  ready: boolean;
  pending: boolean;
  error: string;
  send: (text: string) => Promise<void>;
  reset: () => void;
}

/**
 * Drives a stateless planning interview.
 *
 * The whole history is replayed to the server each turn, so this hook holds
 * the only copy of it. `onTurn` is what makes the hook reusable: it sends the
 * history and returns the next turn, leaving the endpoint to the caller.
 */
export function usePlanChat<TDraft>(
  onTurn: (
    messages: PlanChatMessage[], draft: TDraft | null,
  ) => Promise<PlanTurn<TDraft>>,
): PlanChatState<TDraft> {
  const [messages, setMessages] = useState<PlanChatMessage[]>([]);
  const [draft, setDraft] = useState<TDraft | null>(null);
  const [question, setQuestion] = useState<PlanQuestion | null>(null);
  const [resolved, setResolved] = useState<string[]>([]);
  const [openPoints, setOpenPoints] = useState<string[]>([]);
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);
  const [ready, setReady] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const send = async (text: string) => {
    const said = text.trim();
    if (!said || pending) return;
    const history: PlanChatMessage[] = [
      ...messages, { role: "fde", text: said },
    ];
    setMessages(history); setPending(true); setError(""); setQuestion(null);
    try {
      const turn = await onTurn(history, draft);
      setMessages([...history, { role: "agent", text: turn.reply }]);
      setDraft(turn.draft); setQuestion(turn.question);
      setResolved(turn.resolved); setOpenPoints(turn.open_points);
      setAwaitingConfirmation(turn.awaiting_confirmation);
      setReady(turn.ready);
    } catch (reason) {
      // The FDE's own message stays in the thread so it is not retyped.
      setError(reason instanceof Error ? reason.message : "השיחה נכשלה");
    } finally {
      setPending(false);
    }
  };

  const reset = () => {
    setMessages([]); setDraft(null); setQuestion(null); setResolved([]);
    setOpenPoints([]); setAwaitingConfirmation(false); setReady(false);
    setError("");
  };

  return {
    messages, draft, question, resolved, openPoints, awaitingConfirmation,
    ready, pending, error, send, reset,
  };
}

export function PlanChat<TDraft>({
  chat, title, hint, children,
}: {
  chat: PlanChatState<TDraft>;
  title: string;
  hint: string;
  /** Draft preview rendered under the interview once there is one. */
  children?: ReactNode;
}) {
  const [text, setText] = useState("");

  const say = (said: string) => {
    setText("");
    void chat.send(said);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    // A portal moves the DOM node but not the React tree, so this submit still
    // bubbles into whichever `<form>` mounted the drawer — saving the package
    // or workflow being edited and resetting the editor out from under the
    // interview. `preventDefault` alone does not stop that; the outer handler
    // runs regardless.
    event.stopPropagation();
    say(text);
  };
  // Enter sends, Shift+Enter breaks the line — as in the main composer.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      say(text);
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

      <div className="plan-chat-thread" aria-live="polite">
        {chat.messages.map((message, index) => (
          <p key={index} className={`plan-chat-message ${message.role}`}>
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

      {chat.question && !chat.pending &&
        <QuestionCard question={chat.question} onAnswer={say} />}

      {chat.awaitingConfirmation && !chat.pending &&
        <ConfirmCard onAnswer={say} />}

      <InterviewProgress
        resolved={chat.resolved} openPoints={chat.openPoints} />

      {chat.error && <p className="panel-error" role="alert">{chat.error}</p>}

      {children}

      <form className="plan-chat-composer" onSubmit={submit}>
        <textarea id="plan-chat-input" rows={2} value={text}
          aria-label="תשובה לסוכן" placeholder="ספרו על הנתונים שלכם…"
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

/**
 * The single open question, with the agent's recommendation.
 *
 * Accepting the recommendation is one click because that is the common case;
 * the FDE's own answer is always available in the composer below.
 *
 * When the agent could enumerate the real alternatives it sends `options`,
 * and they replace the lone recommendation button: the first option *is* the
 * recommendation, so accepting it and picking another are the same gesture
 * rather than two competing controls. Options are a shortcut past typing, not
 * a closed menu — the composer stays open underneath, and the agent leaves
 * `options` empty on questions where the FDE's own words are the point.
 */
function QuestionCard({
  question, onAnswer,
}: {
  question: PlanQuestion;
  onAnswer: (text: string) => void;
}) {
  const options = question.options ?? [];
  return (
    <div className="plan-question" role="group"
      aria-label="השאלה הפתוחה של הסוכן">
      <p className="plan-question-text">{question.question}</p>
      {question.recommendation && !options.length &&
        <p className="plan-question-recommendation">
          <strong>המלצה:</strong> {question.recommendation}
        </p>}
      {question.why && <p className="plan-question-why">{question.why}</p>}
      {options.length
        ? <ul className="plan-options">
            {options.map((option, index) => (
              <li key={`${option.label}-${index}`}>
                <button type="button"
                  className={index === 0 ? "plan-option recommended"
                    : "plan-option"}
                  onClick={() => onAnswer(option.answer)}>
                  {/* The agent puts its recommendation first, so the badge
                      is positional rather than a separate flag to keep in
                      sync with the backend. */}
                  {index === 0 &&
                    <ThumbsUp size={14} aria-hidden="true" />}
                  <span>{option.label}</span>
                  {index === 0 && <small>מומלץ</small>}
                </button>
              </li>))}
            <li className="plan-options-other">
              או כתבו תשובה משלכם למטה
            </li>
          </ul>
        : question.recommendation &&
          <button type="button" className="planner-button"
            onClick={() => onAnswer(question.recommendation)}>
            <ThumbsUp size={16} aria-hidden="true" /> מקבל את ההמלצה
          </button>}
    </div>
  );
}

/** The interview does not act before the FDE confirms the summary above. */
function ConfirmCard({ onAnswer }: { onAnswer: (text: string) => void }) {
  return (
    <div className="plan-confirm" role="group" aria-label="אישור סיכום">
      <p>הסוכן סיים לשאול. מאשרים את הסיכום שלמעלה?</p>
      <div className="plan-confirm-actions">
        <button type="button" className="planner-button"
          onClick={() => onAnswer("מאשר, הגענו להסכמה.")}>
          <CheckCircle2 size={16} aria-hidden="true" /> מאשר
        </button>
        <button type="button" className="secondary-button"
          onClick={() => onAnswer("עוד לא — יש נקודה שצריך לחדד.")}>
          עוד לא
        </button>
      </div>
    </div>
  );
}

/**
 * The agent as an offer, not an obligation.
 *
 * Filling the form by hand is the default path and stays untouched behind
 * this. The interview is one button away for an FDE who wants it, and closing
 * the drawer keeps the conversation — reopening resumes rather than restarts.
 *
 * The drawer is portalled to the body because both studio editors mount this
 * inside their own `<form>`, and the interview composer is a form too. Nested
 * forms are invalid HTML: the browser drops the inner one, so every send would
 * submit the package or workflow being edited instead of talking to the agent.
 * `position: fixed` moves the drawer visually but not in the DOM, so only the
 * portal actually takes it out of the surrounding form.
 *
 * The portal fixes the DOM nesting but *not* the React tree: events still
 * propagate to the React parent, so a submit inside the drawer would reach the
 * editor's `onSubmit` and save the very draft under discussion. That is why
 * the drawer stops submit and Enter at its own boundary rather than relying on
 * the portal alone.
 */
export function PlanChatDrawer({
  open, onOpen, onClose, label, busy, disabled, disabledHint, children,
}: {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  label: string;
  /** Reflects an interview still running while the drawer is shut. */
  busy?: boolean;
  /** Blocks opening while a precondition of the interview is unmet. */
  disabled?: boolean;
  /** Why it is blocked — shown as the button's title so it is discoverable. */
  disabledHint?: string;
  children: ReactNode;
}) {
  // A `title` on a disabled button is not reliably announced, so the reason is
  // visible text tied to the button by `aria-describedby`.
  const hintId = "agent-chat-hint";
  return (
    <>
      <div className="agent-chat-launch">
        <button type="button" className="agent-chat-button" onClick={onOpen}
          aria-expanded={open} disabled={disabled}
          aria-describedby={disabled && disabledHint ? hintId : undefined}>
          {busy
            ? <LoaderCircle className="spin" size={16} aria-hidden="true" />
            : <Sparkles size={16} aria-hidden="true" />}
          <span>{label}</span>
        </button>
        {disabled && disabledHint &&
          <p id={hintId} className="agent-chat-hint">{disabledHint}</p>}
      </div>
      {open && createPortal(
        // Everything inside the drawer is contained here. The portal escapes
        // the DOM nesting but not the React tree, so without these guards a
        // submit or an Enter keypress in the interview reaches the editor
        // `<form>` that mounted it and saves the draft being discussed.
        <div className="agent-chat-drawer" role="dialog"
          aria-modal="false" aria-label={label}
          onSubmit={(event) => event.stopPropagation()}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.stopPropagation();
          }}>
          <button type="button" className="agent-chat-close" onClick={onClose}
            aria-label="סגירת השיחה">
            <X size={17} aria-hidden="true" />
          </button>
          {children}
        </div>,
        document.body)}
    </>
  );
}

/**
 * The agent attached to one field: a small button by the label, and the
 * conversation in a popover anchored beside it.
 *
 * This is the per-field counterpart to `PlanChatDrawer`. The drawer covers the
 * form to discuss the whole tool; here the FDE points at the field they cannot
 * word, and the agent talks about that field alone with the form still on
 * screen behind it — so the value being negotiated stays next to the field it
 * lands in.
 *
 * It carries the same two hazards as the drawer, for the same reason: it
 * mounts inside the editor's `<form>`, so it is portalled out of that DOM
 * nesting, and because a portal still propagates through the React tree it
 * also stops `submit` and `Enter` at its own boundary. Without both, sending a
 * message would save the draft under discussion.
 */
export function FieldAgentPopover({
  open, onOpen, onClose, label, field, busy, disabled, disabledHint, children,
}: {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  /** The field's own label, so the button names what it will discuss. */
  label: string;
  /** Distinguishes this popover's ids from every other field's. */
  field: string;
  busy?: boolean;
  disabled?: boolean;
  disabledHint?: string;
  children: ReactNode;
}) {
  const anchor = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<{ top: number; left: number } | null>(null);

  // The popover is portalled to the body, so it cannot be positioned by the
  // anchor's containing block — it is placed from viewport coordinates, and
  // those change whenever the studio form scrolls or the window resizes.
  useLayoutEffect(() => {
    if (!open) return undefined;
    const place = () => {
      const box = anchor.current?.getBoundingClientRect();
      if (box) setAt({ top: box.bottom + 8, left: box.left });
    };
    place();
    // `true` catches the studio form's own scrolling, not just the window's:
    // scroll does not bubble, so a listener on window alone would leave the
    // popover behind while the field it points at moves away.
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open]);

  // Esc closes, matching the expanded canvas and every other layer here.
  useEffect(() => {
    if (!open) return undefined;
    const onEsc = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [open, onClose]);

  const hintId = `field-agent-hint-${field}`;
  return (
    <>
      <div className="field-agent-anchor" ref={anchor}>
        <button type="button" className="field-agent-button" onClick={onOpen}
          aria-expanded={open} disabled={disabled}
          aria-describedby={disabled && disabledHint ? hintId : undefined}
          aria-label={`שאלו את הסוכן על ${label}`}
          title={disabled ? disabledHint : `שאלו את הסוכן על ${label}`}>
          {busy
            ? <LoaderCircle className="spin" size={15} aria-hidden="true" />
            : <Sparkles size={15} aria-hidden="true" />}
        </button>
        {disabled && disabledHint &&
          <span id={hintId} className="field-agent-hint">{disabledHint}</span>}
      </div>
      {open && at !== null && createPortal(
        <div className="field-agent-popover" role="dialog" aria-modal="false"
          aria-label={`הסוכן · ${label}`}
          style={{ top: at.top, left: at.left }}
          onSubmit={(event) => event.stopPropagation()}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.stopPropagation();
          }}>
          <header className="field-agent-popover-header">
            <span>{label}</span>
            <button type="button" className="agent-chat-close" onClick={onClose}
              aria-label="סגירת השיחה">
              <X size={16} aria-hidden="true" />
            </button>
          </header>
          {children}
        </div>,
        document.body)}
    </>
  );
}

function InterviewProgress({
  resolved, openPoints,
}: {
  resolved: string[];
  openPoints: string[];
}) {
  if (!resolved.length && !openPoints.length) return null;
  return (
    <div className="plan-progress">
      {!!resolved.length && <section>
        <h4><CheckCircle2 size={14} aria-hidden="true" /> סוכם</h4>
        <ul>{resolved.map((item, index) => <li key={index}>{item}</li>)}</ul>
      </section>}
      {!!openPoints.length && <section>
        <h4><CircleDot size={14} aria-hidden="true" /> נשאר פתוח</h4>
        <ul>{openPoints.map((item, index) => <li key={index}>{item}</li>)}</ul>
      </section>}
    </div>
  );
}
