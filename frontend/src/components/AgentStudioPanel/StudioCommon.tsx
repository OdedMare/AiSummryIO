"use client";

import { FormEvent, useState } from "react";
import {
  AlertTriangle, CheckCircle2, KeyRound, Send,
} from "lucide-react";
import { api } from "@/services/api";

export function StudioLogin({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setLoading(true); setError("");
    try {
      await api.login(password); setPassword(""); onLogin();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ההתחברות נכשלה");
    } finally {
      setLoading(false);
    }
  };
  return (
    <form className="admin-login" onSubmit={submit}>
      <span className="login-icon"><KeyRound size={24} /></span>
      <h3>כניסת מנהל מערכת</h3>
      <p>כאן מנהלים מקורות מידע, תהליכי סיכום ו־Skills.</p>
      <label><span>סיסמה</span><input type="password" value={password}
        onChange={(event) => setPassword(event.target.value)}
        autoComplete="current-password" autoFocus />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button" type="submit"
        disabled={loading || !password}>
        <Send size={17} /> {loading ? "מתחבר…" : "כניסה לסטודיו"}
      </button>
    </form>
  );
}

export function ReviewQueue({
  items,
}: {
  items: Array<Record<string, unknown>>;
}) {
  return (
    <section className="review-queue">
      <header><div><h3>תור שיפור</h3>
        <p>סיכומים שסומנו ודורשים בדיקת מנהל.</p>
      </div><span>{items.length} פריטים</span></header>
      {items.map((item) => <ReviewItem key={String(item.id)} item={item} />)}
      {!items.length && <p className="panel-empty">
        <CheckCircle2 size={18} /> אין פריטים פתוחים.
      </p>}
    </section>
  );
}

function ReviewItem({ item }: { item: Record<string, unknown> }) {
  return (
    <article>
      <span className="review-icon"><AlertTriangle size={18} /></span>
      <div><strong>{String(item.comment || "סיכום דורש שיפור")}</strong>
        <small dir="ltr">run {String(item.run_id)} · {String(item.run_status)}
        </small>
      </div>
    </article>
  );
}
