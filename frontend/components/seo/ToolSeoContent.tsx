import Link from "next/link";
import { Container } from "@/components/ui";

type ToolSeoContentProps = { title: string; intro: string; points: string[]; steps: string[]; links?: { href: string; label: string }[] };
export function ToolSeoContent({ title, intro, points, steps, links = [] }: ToolSeoContentProps) {
  return <Container><article className="target-size-content"><section><h2>{title}</h2><p>{intro}</p></section><section><h2>How it works</h2><ol>{steps.map((step) => <li key={step}>{step}</li>)}</ol></section><section><h2>Why use FluxFile?</h2><ul>{points.map((point) => <li key={point}>{point}</li>)}</ul></section>{links.length > 0 && <nav aria-label="Related file tools">{links.map((link) => <Link key={link.href} href={link.href}>{link.label}</Link>)}</nav>}</article></Container>;
}
