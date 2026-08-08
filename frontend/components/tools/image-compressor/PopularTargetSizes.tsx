import Link from "next/link";
import { imageTargetPages } from "@/lib/image-target-pages";

export function PopularTargetSizes() {
  return <section className="popular-target-sizes" aria-labelledby="popular-target-sizes-title">
    <h2 id="popular-target-sizes-title">Popular target sizes</h2>
    <nav aria-label="Popular image target sizes">
      {imageTargetPages.map((page) => <Link key={page.slug} href={`/${page.slug}`}>{page.targetKb} KB</Link>)}
    </nav>
  </section>;
}
