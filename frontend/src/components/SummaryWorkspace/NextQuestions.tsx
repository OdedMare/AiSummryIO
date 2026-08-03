import { CornerDownLeft } from "lucide-react";
import type { SummaryResult } from "@/types";

/**
 * Where the conversation can go next.
 *
 * The backend has always returned `suggested_questions` and the UI never
 * showed them, leaving the user to invent a follow-up against a catalog they
 * cannot see. These are questions the agent can answer, offered so the user
 * can keep asking without composing one — clicking asks it immediately.
 *
 * This never asks the user anything. It only hands them their next question,
 * and the composer below stays the way to ask something else entirely.
 */
export default function NextQuestions({
  result, onAsk,
}: {
  result: SummaryResult;
  onAsk: (question: string) => void;
}) {
  const questions = result.suggested_questions ?? [];
  if (!questions.length) return null;
  return (
    <section className="next-questions" aria-labelledby="next-questions-title">
      <h2 id="next-questions-title">להמשיך לשאול</h2>
      <ul>
        {questions.slice(0, 4).map((question) => (
          <li key={question}>
            <button type="button" className="next-question"
              onClick={() => onAsk(question)}>
              <CornerDownLeft size={13} aria-hidden="true" />
              <span>{question}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
