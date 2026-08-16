import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { LoaderCircle, Sparkles, X } from "lucide-react";

export function PlanChatDrawer({
  open,
  onOpen,
  onClose,
  label,
  busy,
  disabled,
  disabledHint,
  children,
}: {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  label: string;
  busy?: boolean;
  disabled?: boolean;
  disabledHint?: string;
  children: ReactNode;
}) {
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
        {disabled && disabledHint
          && <p id={hintId} className="agent-chat-hint">{disabledHint}</p>}
      </div>
      {open && createPortal(
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
        document.body,
      )}
    </>
  );
}

export function FieldAgentPopover({
  open,
  onOpen,
  onClose,
  label,
  field,
  busy,
  disabled,
  disabledHint,
  children,
}: {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  label: string;
  field: string;
  busy?: boolean;
  disabled?: boolean;
  disabledHint?: string;
  children: ReactNode;
}) {
  const anchor = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    if (!open) return undefined;
    const place = () => {
      const box = anchor.current?.getBoundingClientRect();
      if (box) setAt({ top: box.bottom + 8, left: box.left });
    };
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
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
        {disabled && disabledHint
          && <span id={hintId} className="field-agent-hint">
            {disabledHint}
          </span>}
      </div>
      {open && at !== null && createPortal(
        <div className="field-agent-popover" role="dialog" aria-modal="false"
          aria-label={`הסוכן · ${label}`} style={{ top: at.top, left: at.left }}
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
        document.body,
      )}
    </>
  );
}
