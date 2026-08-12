import { ApplicationShell } from "@/components/layout";
import { Badge, Card, Container } from "@/components/ui";

const benefits = ["Generous limits", "No watermark", "Private temporary storage", "Fast processing"];
const steps = ["Choose a tool", "Choose a file", "Process", "Download"];

export default function Home() {
  return (
    <ApplicationShell>
      <Container>
        <main className="landing-page">
          <section className="landing-hero">
            <Badge tone="primary">FileMino</Badge>
            <h1>
              Fast tools for{" "}
              <span className="landing-hero-accent">everyday files.</span>
            </h1>
            <p>Compress, convert and optimize without unnecessary complexity.</p>
          </section>

          <section className="landing-support">
            <Card className="landing-info-card">
              <h2>Why FileMino</h2>
              <ul>
                {benefits.map((benefit) => (
                  <li key={benefit}>{benefit}</li>
                ))}
              </ul>
            </Card>
            <Card className="landing-info-card">
              <h2>How it works</h2>
              <ol>
                {steps.map((step, index) => (
                  <li key={step}>
                    <span>{index + 1}</span>
                    {step}
                  </li>
                ))}
              </ol>
            </Card>
          </section>

          <section id="about" className="sr-only">About FileMino</section>
          <section id="privacy" className="sr-only">Privacy</section>
          <section id="terms" className="sr-only">Terms</section>
        </main>
      </Container>
    </ApplicationShell>
  );
}
