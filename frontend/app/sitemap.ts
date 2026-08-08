import type { MetadataRoute } from "next";
import { imageTargetPages } from "@/lib/image-target-pages";
import { getAbsoluteUrl } from "@/lib/site-url";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: getAbsoluteUrl("/"), changeFrequency: "monthly", priority: 1 },
    { url: getAbsoluteUrl("/image-compressor"), changeFrequency: "monthly", priority: 0.9 },
    { url: getAbsoluteUrl("/video-compressor"), changeFrequency: "monthly", priority: 0.8 },
    ...imageTargetPages.map((page) => ({
      url: getAbsoluteUrl(`/${page.slug}`),
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
  ];
}
