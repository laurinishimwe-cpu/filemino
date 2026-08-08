import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";
type BadgeProps = HTMLAttributes<HTMLSpanElement> & { tone?: "neutral" | "primary" | "success" | "warning" | "error" };
export function Badge({ className, tone = "neutral", ...props }: BadgeProps) { return <span className={cn("ui-badge", `ui-badge-${tone}`, className)} {...props} />; }
