"use client";
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Button } from "./Button";
type ModalProps = { open: boolean; onClose: () => void; title: string; description?: string; children?: ReactNode; primaryAction?: { label: string; onClick: () => void; loading?: boolean }; secondaryAction?: { label: string; onClick: () => void }; destructiveAction?: { label: string; onClick: () => void }; width?: "sm" | "md" | "lg" };
const widths = { sm: "24rem", md: "32rem", lg: "42rem" };
export function Modal({ open, onClose, title, description, children, primaryAction, secondaryAction, destructiveAction, width = "md" }: ModalProps) {
  const [mounted, setMounted] = useState(false); const [visible, setVisible] = useState(false); const panel = useRef<HTMLDivElement>(null); const previous = useRef<HTMLElement | null>(null); const titleId = useId(); const descriptionId = useId();
  useEffect(() => {
    if (open && !mounted) {
      previous.current = document.activeElement as HTMLElement;
      document.body.style.overflow = "hidden";
      const mountFrame = requestAnimationFrame(() => {
        setMounted(true);
        requestAnimationFrame(() => setVisible(true));
      });
      return () => cancelAnimationFrame(mountFrame);
    }

    if (!open && mounted) {
      const closeFrame = requestAnimationFrame(() => setVisible(false));
      const exitDuration = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--duration-normal"));
      const timer = window.setTimeout(() => {
        setMounted(false);
        previous.current?.focus();
      }, exitDuration);
      document.body.style.overflow = "";
      return () => { cancelAnimationFrame(closeFrame); window.clearTimeout(timer); };
    }
  }, [open, mounted]);
  useEffect(() => { if (!open) return; const keydown = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); if (event.key === "Tab" && panel.current) { const focusable = panel.current.querySelectorAll<HTMLElement>('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'); const first = focusable[0]; const last = focusable[focusable.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); } } }; document.addEventListener("keydown", keydown); window.setTimeout(() => panel.current?.querySelector<HTMLElement>("button")?.focus(), 0); return () => document.removeEventListener("keydown", keydown); }, [open, onClose]);
  if (!mounted) return null;
  return createPortal(<div className={`ui-modal-overlay ${visible ? "ui-modal-open" : "ui-modal-closing"}`} role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><div ref={panel} className="ui-modal-panel" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={description ? descriptionId : undefined} style={{ "--modal-width": widths[width] } as CSSProperties}><div className="p-6"><div className="flex items-start justify-between gap-4"><div><h2 id={titleId} className="text-xl font-semibold text-text-primary">{title}</h2>{description && <p id={descriptionId} className="mt-2 text-sm text-text-secondary">{description}</p>}</div><button className="ui-button ui-button-ghost min-h-0 p-2" onClick={onClose} aria-label="Close dialog">×</button></div>{children && <div className="mt-6">{children}</div>} {(primaryAction || secondaryAction || destructiveAction) && <div className="mt-6 flex flex-wrap justify-end gap-2">{secondaryAction && <Button variant="secondary" onClick={secondaryAction.onClick}>{secondaryAction.label}</Button>}{destructiveAction && <Button variant="destructive" onClick={destructiveAction.onClick}>{destructiveAction.label}</Button>}{primaryAction && <Button loading={primaryAction.loading} onClick={primaryAction.onClick}>{primaryAction.label}</Button>}</div>}</div></div></div>, document.body);
}
