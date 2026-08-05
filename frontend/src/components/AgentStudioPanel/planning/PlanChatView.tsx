import { useState } from "react";
import type {
  FormEvent,
  KeyboardEvent,
  ReactNode,
} from "react";
import {
  CheckCircle2,
  CircleDot,
  LoaderCircle,
  MessagesSquare,
  Send,
  ThumbsUp,
} from "lucide-react";
import type { PlanQuestion } from "@/types";
import type { PlanChatState } from "./usePlanChat";

export function PlanChat<TDraft>({
  chat,
  title,
  hint,
  children,
}: {
  chat: PlanChatState<TDraft>;
  title: string;
  hint: string;
  children?: ReactNode;
}) {
  const [text, setText] = useState("");
  const say = (said: string) => {
    setText("");
    void chat.send(said);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    event.stopPropagation();
    say(text);
  };
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
        <div><h3 id="plan-chat-title">{title}</h3><p>{hint}</p></div>
        {!!chat.messages.length
          && <button type="button" className="plan-chat-reset"
            onClick={chat.reset} disabled={chat.pending}>שיחה חדשה</button>}
      </header>
      <div className="plan-chat-thread" aria-live="polite">
        {chat.messages.map((message, index) =>
          <p key={index} className={`plan-chat-message ${message.role}`}>
            <span className="plan-chat-role">
              {message.role === "fde" ? "אני" : "הסוכן"}
            </span>
            {message.text}
          </p>)}
        {chat.pending && <p className="plan-chat-message agent pending">
          <LoaderCircle className="spin" size={15} aria-hidden="true" />
          הסוכן חושב…
        </p>}
        {!chat.messages.length && !chat.pending
          && <p className="panel-empty">{hint}</p>}
      </div>
      {chat.question && !chat.pending
        && <QuestionCard question={chat.question} onAnswer={say} />}
      {chat.awaitingConfirmation && !chat.pending
        && <ConfirmCard onConfirm={chat.confirm} onRevise={say} />}
      <InterviewProgress resolved={chat.resolved} openPoints={chat.openPoints} />
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

function QuestionCard({
  question,
  onAnswer,
}: {
  question: PlanQuestion;
  onAnswer: (text: string) => void;
}) {
  const options = question.options ?? [];
  return (
    <div className="plan-question" role="group"
      aria-label="השאלה הפתוחה של הסוכן">
      <p className="plan-question-text">{question.question}</p>
      {question.recommendation && !options.length
        && <p className="plan-question-recommendation">
          <strong>המלצה:</strong> {question.recommendation}
        </p>}
      {question.why && <p className="plan-question-why">{question.why}</p>}
      {options.length
        ? <ul className="plan-options">
          {options.map((option, index) =>
            <li key={`${option.label}-${index}`}>
              <button type="button"
                className={index === 0
                  ? "plan-option recommended"
                  : "plan-option"}
                onClick={() => onAnswer(option.answer)}>
                {index === 0 && <ThumbsUp size={14} aria-hidden="true" />}
                <span>{option.label}</span>
                {index === 0 && <small>מומלץ</small>}
              </button>
            </li>)}
          <li className="plan-options-other">או כתבו תשובה משלכם למטה</li>
        </ul>
        : question.recommendation
          && <button type="button" className="planner-button"
            onClick={() => onAnswer(question.recommendation)}>
            <ThumbsUp size={16} aria-hidden="true" /> מקבל את ההמלצה
          </button>}
    </div>
  );
}

function ConfirmCard({
  onConfirm,
  onRevise,
}: {
  onConfirm: () => void;
  onRevise: (text: string) => void;
}) {
  return (
    <div className="plan-confirm" role="group" aria-label="אישור סיכום">
      <p>הסוכן סיים לשאול. מאשרים את הסיכום שלמעלה?</p>
      <div className="plan-confirm-actions">
        <button type="button" className="planner-button" onClick={onConfirm}>
          <CheckCircle2 size={16} aria-hidden="true" /> מאשר
        </button>
        <button type="button" className="secondary-button"
          onClick={() => onRevise("עוד לא — יש נקודה שצריך לחדד.")}>
          עוד לא
        </button>
      </div>
    </div>
  );
}

function InterviewProgress({
  resolved,
  openPoints,
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
