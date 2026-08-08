import { cn } from "@/lib/cn";
type ProgressProps = { value?: number; indeterminate?: boolean; showPercentage?: boolean; status?: string; size?: "sm" | "md"; className?: string };
export function Progress({ value = 0, indeterminate = false, showPercentage = false, status, size = "md", className }: ProgressProps) {
  const safeValue = Math.min(100, Math.max(0, value));
  const height = size === "sm" ? "h-1.5" : "h-2.5";

  return (
    <div className={cn("w-full", className)}>
      {status && <p className="mb-2 text-sm text-text-secondary" aria-live="polite">{status}</p>}
      <div className={cn("ui-progress-track", height)} role="progressbar" aria-label={status ?? "Progress"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={indeterminate ? undefined : safeValue}>
        <div className={cn("ui-progress-bar", indeterminate && "ui-progress-indeterminate")} style={indeterminate ? undefined : { width: `${safeValue}%` }} />
      </div>
      {showPercentage && !indeterminate && <p className="mt-2 text-right text-xs text-text-secondary">{safeValue}%</p>}
    </div>
  );
}
