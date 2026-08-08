import { Container } from "@/components/ui";
import { ToolRail } from "@/components/tools";
import { fluxFileTools } from "@/lib/tools";

export function ToolBar() {
  return (
    <div className="tool-bar" id="tools">
      <Container className="tool-bar-inner">
        <ToolRail tools={fluxFileTools} label="FluxFile tools" />
      </Container>
    </div>
  );
}
