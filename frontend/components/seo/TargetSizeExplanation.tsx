import type { ImageTargetPage } from "@/lib/image-target-pages";

export function TargetSizeExplanation({ page }: { page: ImageTargetPage }) {
  return <section className="target-size-explanation" aria-labelledby="target-size-explanation-title">
    <h2 id="target-size-explanation-title">How {page.targetKb} KB image compression works</h2>
    <p>{page.explanation}</p>
    <p>FluxFile aims for the highest-quality result at or below your selected target, rather than promising an exact file size.</p>
  </section>;
}
