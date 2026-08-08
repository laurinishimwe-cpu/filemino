import { ApplicationShell } from "@/components/layout";
import { Badge, Card, Container } from "@/components/ui";

export default function Home() {
  return <ApplicationShell><Container><section className="tool-page" id="tools"><div className="tool-header"><div className="tool-header-badge"><Badge tone="primary">File tools</Badge></div><h1 className="tool-header-title">Simple tools for your files.</h1><p className="tool-header-description">Choose a task, add a file, and get a useful result—without unnecessary complexity.</p></div><Card className="p-6 text-center"><h2 className="text-xl font-semibold text-text-primary">Tools are on their way</h2><p className="mt-2 text-sm text-text-secondary">The shared shell and processing components are ready for upcoming file utilities.</p></Card></section><section id="about" className="sr-only">About FluxFile</section><section id="privacy" className="sr-only">Privacy</section><section id="terms" className="sr-only">Terms</section></Container></ApplicationShell>;
}
