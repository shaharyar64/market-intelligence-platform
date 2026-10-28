"use client";

import { ReactNode, useRef, useState } from "react";

/**
 * Lightweight hover tooltip that matches the dashboard design language.
 * Renders with position: fixed (computed from the trigger's rect) so it is
 * never clipped by ancestors that use overflow-hidden (e.g. the topbar).
 */
export default function InfoTooltip({
  content,
  children,
  maxWidth = 300,
}: {
  content?: string | null;
  children: ReactNode;
  maxWidth?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  if (!content) return <>{children}</>;

  const place = () => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const half = maxWidth / 2 + 12;
    const left = Math.min(Math.max(r.left + r.width / 2, half), window.innerWidth - half);
    setPos({ top: r.bottom + 10, left });
  };

  return (
    <div
      ref={ref}
      className="inline-flex"
      onMouseEnter={() => { place(); setShow(true); }}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div
          role="tooltip"
          style={{
            position: "fixed",
            top: pos.top,
            left: pos.left,
            transform: "translateX(-50%)",
            zIndex: 60,
            maxWidth,
            background: "var(--dropdown-bg)",
            border: "1px solid var(--card-bd)",
            color: "var(--body-tx)",
            backdropFilter: "var(--blur)",
            WebkitBackdropFilter: "var(--blur)",
            boxShadow: "0 12px 32px rgba(15,23,42,0.18)",
          }}
          className="pointer-events-none rounded-xl px-3 py-2 text-xs leading-relaxed"
        >
          {content}
        </div>
      )}
    </div>
  );
}
