import { Container } from "@/components/ui";
import { ToolRail } from "@/components/tools";
import { fileMinoTools } from "@/lib/tools";

export function ToolBar() {
  return (
    <div className="tool-bar" id="tools">
      <Container className="tool-bar-inner">
        <ToolRail tools={fileMinoTools} label="FileMino tools" />
      </Container>
    </div>
  );
}
