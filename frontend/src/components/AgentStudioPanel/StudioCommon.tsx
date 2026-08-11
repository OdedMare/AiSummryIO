"use client";

import { AlertTriangle, CheckCircle2, Plus, Star } from "lucide-react";

/**
 * "Start a blank one" for a studio list.
 *
 * Every editor edits one row in place, so opening an item takes the form
 * over — without this the only way back to a blank form was the cancel
 * button that appears while editing, which reads as undo rather than as a
 * way to add something. `label` is the accessible name because "חדש" alone
 * does not say what would be created.
 */
export function NewItemButton({
  label, onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button type="button" className="studio-new" onClick={onClick}
      aria-label={label} title={label}>
      <Plus size={15} aria-hidden="true" /> חדש
    </button>
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
  const rating = Number(item.rating);
  return (
    <article>
      <span className="review-icon"><AlertTriangle size={18} /></span>
      <div><strong>{String(item.comment || "סיכום דורש שיפור")}</strong>
        {Number.isFinite(rating) && rating > 0 &&
          <span className="review-rating" aria-label={"דירוג " + rating + " מתוך 5"}>
            {[1, 2, 3, 4, 5].map((value) => (
              <Star key={value} size={13}
                fill={value <= rating ? "currentColor" : "none"} />
            ))}
          </span>}
        <small dir="ltr">run {String(item.run_id)} · {String(item.run_status)}
        </small>
      </div>
    </article>
  );
}
