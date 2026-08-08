"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

type ProgressRingProps = {
  value?: number;
  indeterminate?: boolean;
  label?: string;
  status?: string;
  size?: "sm" | "md";
  className?: string;
  animateFromZero?: boolean;
};

export function ProgressRing({ value = 0, indeterminate = false, label, status, size = "md", className, animateFromZero = false }: ProgressRingProps) {
  const safeValue = Math.min(100, Math.max(0, value));
  const [animatedValue, setAnimatedValue] = useState(animateFromZero ? 0 : safeValue);

  useEffect(() => {
    if (!animateFromZero) return;

    const frame = window.requestAnimationFrame(() => setAnimatedValue(safeValue));
    return () => window.cancelAnimationFrame(frame);
  }, [animateFromZero, safeValue]);

  const circumference = 2 * Math.PI * 18;
  const displayValue = animateFromZero ? animatedValue : safeValue;
  const offset = circumference - displayValue / 100 * circumference;

  return <div className={cn("progress-ring", `progress-ring-${size}`, className)} data-animate-from-zero={animateFromZero || undefined}><div className="progress-ring-visual" role="progressbar" aria-label={label ?? status ?? "Progress"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={indeterminate ? undefined : safeValue}><svg viewBox="0 0 48 48" aria-hidden="true"><circle className="progress-ring-track" cx="24" cy="24" r="18" /><circle className={cn("progress-ring-value", indeterminate && "progress-ring-indeterminate")} cx="24" cy="24" r="18" strokeDasharray={indeterminate ? undefined : circumference} strokeDashoffset={indeterminate ? undefined : offset} /></svg>{!indeterminate && <span className="progress-ring-value-text">{safeValue}%</span>}</div>{label && <p className="progress-ring-label">{label}</p>}{status && <p className="progress-ring-status" aria-live="polite">{status}</p>}</div>;
}
