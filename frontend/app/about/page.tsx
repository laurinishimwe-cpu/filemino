import type { Metadata } from "next";
import { ApplicationShell } from "@/components/layout";
import { Container } from "@/components/ui";

export const metadata: Metadata = { title: "About FluxFile", description: "Learn about FluxFile’s simple online tools for compressing and converting everyday files.", alternates: { canonical: "/about" } };
export default function AboutPage() { return <ApplicationShell><Container><main className="target-size-content"><h1>About FluxFile</h1><p>FluxFile builds straightforward online tools for everyday file tasks. The current tools compress videos and images, and convert common image formats.</p><section><h2>Keep file tasks simple</h2><p>Choose a tool, choose a file, adjust only the options you need, then download the result.</p></section><section><h2>Temporary processing</h2><p>FluxFile uses private storage patterns and temporary retention settings for uploaded files and generated results. Availability and retention are controlled by the active deployment configuration.</p></section></main></Container></ApplicationShell>; }
