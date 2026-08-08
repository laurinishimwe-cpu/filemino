import { ApplicationShell } from "@/components/layout";
import { Container } from "@/components/ui";
import { ImageCompressor } from "@/components/tools/image-compressor/ImageCompressor";
import type { ImageTargetPage as ImageTargetPageData } from "@/lib/image-target-pages";
import { TargetSizeExplanation } from "./TargetSizeExplanation";
import { TargetSizeFAQ } from "./TargetSizeFAQ";

export function TargetSizePage({ page }: { page: ImageTargetPageData }) {
  const targetLabel = `${page.targetKb} KB`;
  return <ApplicationShell>
    <ImageCompressor
      initialTargetSizeKb={page.targetKb}
      initialOutputFormat="auto"
      initialAllowResizeForTarget
      title={`Compress Image to ${targetLabel}`}
      description={`Reduce JPG, PNG or WebP images to ${targetLabel} or less while preserving as much visual quality as possible.`}
      supportingInfo="JPG, PNG and WebP supported"
    />
    <Container>
      <article className="target-size-content">
        <TargetSizeExplanation page={page} />
        <TargetSizeFAQ page={page} />
      </article>
    </Container>
  </ApplicationShell>;
}
