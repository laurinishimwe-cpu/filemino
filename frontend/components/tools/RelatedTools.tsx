import { relatedFileMinoTools } from "@/lib/tools";
import { ToolRail } from "./ToolRail";

type RelatedToolsProps = { currentTool: string };

export function RelatedTools({ currentTool }: RelatedToolsProps) {
  const tools = relatedFileMinoTools.filter((tool) => tool.name !== currentTool);
  return <section className="related-tools" aria-labelledby="related-tools-title"><h2 className="related-tools-title" id="related-tools-title">More file tools</h2><p className="related-tools-description">More focused utilities are coming soon.</p><ToolRail tools={tools} label="Related FileMino tools" compact /></section>;
}
