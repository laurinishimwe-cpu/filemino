import type { ReactNode } from "react";
import { Container } from "@/components/ui";
import { ToolHeader } from "./ToolHeader";

type ToolPageProps = { title: string; description: string; badge?: ReactNode; supportingInfo?: ReactNode; children: ReactNode };
export function ToolPage({ title, description, badge, supportingInfo, children }: ToolPageProps) {
  return <Container><section className="tool-page"><ToolHeader title={title} description={description} badge={badge} supportingInfo={supportingInfo} />{children}</section></Container>;
}
