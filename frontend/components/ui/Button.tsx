import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "destructive"; loading?: boolean };
export function Button({ className, variant = "primary", loading = false, disabled, children, ...props }: ButtonProps) {
  return <button className={cn("ui-button", `ui-button-${variant}`, className)} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>{loading && <span className="ui-spinner" aria-hidden="true" />}{children}</button>;
}
