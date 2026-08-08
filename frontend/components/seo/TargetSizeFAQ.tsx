import type { ImageTargetPage } from "@/lib/image-target-pages";

export function TargetSizeFAQ({ page }: { page: ImageTargetPage }) {
  return <section className="target-size-faq" aria-labelledby="target-size-faq-title">
    <h2 id="target-size-faq-title">Questions about compressing to {page.targetKb} KB</h2>
    <dl>
      {page.faqs.map((faq) => <div key={faq.question}><dt>{faq.question}</dt><dd>{faq.answer}</dd></div>)}
    </dl>
  </section>;
}
