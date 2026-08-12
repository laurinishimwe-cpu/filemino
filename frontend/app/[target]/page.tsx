import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { TargetSizePage } from "@/components/seo/TargetSizePage";
import { getImageTargetPage, imageTargetPages } from "@/lib/image-target-pages";
import { getAbsoluteUrl } from "@/lib/site-url";
import { ConversionSeoPage } from "@/components/seo/ConversionSeoPage";
import { conversionPages, getConversionPage } from "@/lib/conversion-pages";

type TargetPageProps = { params: Promise<{ target: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return [...imageTargetPages, ...conversionPages].map((page) => ({ target: page.slug }));
}

export async function generateMetadata({ params }: TargetPageProps): Promise<Metadata> {
  const { target } = await params;
  const page = getImageTargetPage(target) ?? getConversionPage(target);
  if (!page) return {};
  const path = `/${page.slug}`;
  return {
    title: page.title,
    description: page.description,
    alternates: { canonical: path },
    openGraph: {
      title: page.title,
      description: page.description,
      url: getAbsoluteUrl(path),
      type: "website",
    },
  };
}

export default async function TargetPage({ params }: TargetPageProps) {
  const { target } = await params;
  const targetPage = getImageTargetPage(target);
  if (targetPage) return <TargetSizePage page={targetPage} />;
  const conversionPage = getConversionPage(target);
  if (conversionPage) return <ConversionSeoPage page={conversionPage} />;
  notFound();
}
