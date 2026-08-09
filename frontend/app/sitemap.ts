import type { MetadataRoute } from "next";
import { imageTargetPages } from "@/lib/image-target-pages";
import { getAbsoluteUrl } from "@/lib/site-url";
import { conversionPages } from "@/lib/conversion-pages";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: getAbsoluteUrl("/"), changeFrequency: "monthly", priority: 1 },
    { url: getAbsoluteUrl("/image-compressor"), changeFrequency: "monthly", priority: 0.9 },
    { url: getAbsoluteUrl("/video-compressor"), changeFrequency: "monthly", priority: 0.8 },
    { url: getAbsoluteUrl("/image-converter"), changeFrequency: "monthly", priority: 0.8 },
    { url: getAbsoluteUrl("/about"), changeFrequency: "yearly", priority: 0.4 },
    ...imageTargetPages.map((page) => ({
      url: getAbsoluteUrl(`/${page.slug}`),
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
    ...conversionPages.map((page) => ({ url: getAbsoluteUrl(`/${page.slug}`), changeFrequency: "monthly" as const, priority: 0.7 })),
  ];
}
