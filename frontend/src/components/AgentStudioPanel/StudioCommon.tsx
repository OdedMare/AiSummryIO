"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";

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
