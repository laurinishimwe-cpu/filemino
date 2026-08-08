import type { ReactNode } from "react";
import { Badge } from "@/components/ui";

type ToolHeaderProps = { title: string; description: string; badge?: ReactNode; supportingInfo?: ReactNode };
export function ToolHeader({ title, description, badge, supportingInfo }: ToolHeaderProps) {
  return <header className="tool-header">{badge && <div className="tool-header-badge">{typeof badge === "string" ? <Badge tone="primary">{badge}</Badge> : badge}</div>}<h1 className="tool-header-title">{title}</h1><p className="tool-header-description">{description}</p>{supportingInfo && <div className="tool-header-supporting">{supportingInfo}</div>}</header>;
}
