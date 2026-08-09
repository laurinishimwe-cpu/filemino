import { ApplicationShell } from "@/components/layout";
import { Container } from "@/components/ui";
import { ImageConverter } from "@/components/tools/image-converter/ImageConverter";
import type { ConversionPage } from "@/lib/conversion-pages";

export function ConversionSeoPage({ page }: { page: ConversionPage }) {
  return <ApplicationShell><ImageConverter initialTarget={page.target} title={page.heading} description={page.intro} /><Container><article className="target-size-content"><section><h2>About this conversion</h2><p>{page.intro}</p></section><section><h2>Good to know</h2><ul>{page.notes.map((note) => <li key={note}>{note}</li>)}</ul></section></article></Container></ApplicationShell>;
}
