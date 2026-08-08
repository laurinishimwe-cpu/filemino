import type { ReactNode } from "react";
import { Button, Card } from "@/components/ui";

type ToolErrorCardProps = {
  title: string;
  message: string | null;
  onRetry: () => void;
  onReset: () => void;
  resetLabel: string;
  actions?: ReactNode;
};

export function ToolErrorCard({ title, message, onRetry, onReset, resetLabel, actions }: ToolErrorCardProps) {
  if (!message) return null;

  return <Card className="tool-error" role="alert"><h2 className="tool-error-title">{title}</h2><p className="tool-error-message">{message}</p>{actions}<div className="tool-cta"><Button onClick={onRetry}>Try again</Button><Button variant="secondary" onClick={onReset}>{resetLabel}</Button></div></Card>;
}
