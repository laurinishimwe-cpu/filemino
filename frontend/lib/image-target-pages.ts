export type TargetSizeFaq = { question: string; answer: string };

export type ImageTargetPage = {
  slug: string;
  targetKb: number;
  title: string;
  description: string;
  explanation: string;
  qualityNote: string;
  faqs: TargetSizeFaq[];
};

const sharedFaqs: TargetSizeFaq[] = [
  {
    question: "Which image formats can I compress?",
    answer: "FluxFile supports JPG, PNG, and WebP. PNG transparency is preserved when keeping PNG or choosing WebP.",
  },
  {
    question: "Are images processed privately?",
    answer: "Files are processed temporarily and are not made public. Download your result, then process another image whenever you need to.",
  },
];

function targetFaq(targetKb: number, qualityNote: string): TargetSizeFaq[] {
  return [
    {
      question: `Can every image reach ${targetKb} KB?`,
      answer: qualityNote,
    },
    {
      question: "What happens if lowering quality is not enough?",
      answer: "FluxFile first searches for the best quality at the target. If needed, it can reduce dimensions while keeping the original aspect ratio.",
    },
    ...sharedFaqs,
  ];
}

function page(targetKb: number, explanation: string, qualityNote: string): ImageTargetPage {
  const label = `${targetKb} KB`;
  return {
    slug: `compress-image-to-${targetKb}kb`,
    targetKb,
    title: `Compress Image to ${label} Online | FluxFile`,
    description: `Reduce JPG, PNG, or WebP images to ${label} or less while preserving as much visual quality as possible.`,
    explanation,
    qualityNote,
    faqs: targetFaq(targetKb, qualityNote),
  };
}

export const imageTargetPages = [
  page(20, "A 20 KB target is useful for strict upload fields and compact form attachments. Simple graphics usually retain more detail than busy photographs at this size.", "Not always. Detailed photos, gradients, and noise need more data than simple graphics, so a 20 KB target may require a noticeable quality or dimension reduction."),
  page(50, "A 50 KB target works well for lightweight forms, profile images, and quick attachments. The available quality depends on image dimensions and how much visual detail it contains.", "Often, but not universally. FluxFile chooses the highest practical quality at or below 50 KB, and may reduce dimensions when quality changes alone cannot meet the target."),
  page(100, "A 100 KB target is a practical balance for many web uploads. It leaves more room for image detail while still keeping transfers and storage light.", "Many images can reach 100 KB with good clarity, although high-resolution photographs and detailed PNGs may still need a quality or dimension adjustment."),
  page(200, "A 200 KB target suits richer previews, product images, and pages that need a sharper image without a large download. Image complexity still determines the best possible result.", "A 200 KB target is more forgiving than smaller limits, but textured photos and large transparent PNGs can still require a controlled reduction in quality or dimensions."),
  page(500, "A 500 KB target is useful when visual detail matters but the original image is unnecessarily large. It can be a good fit for larger previews and content uploads.", "Many images can preserve substantial detail at 500 KB. Very large, complex images may still need a modest adjustment to achieve the target responsibly."),
] as const;

export function getImageTargetPage(slug: string) {
  return imageTargetPages.find((page) => page.slug === slug);
}
