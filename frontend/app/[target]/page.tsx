import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { TargetSizePage } from "@/components/seo/TargetSizePage";
import { getImageTargetPage, imageTargetPages } from "@/lib/image-target-pages";
import { getAbsoluteUrl } from "@/lib/site-url";

type TargetPageProps = { params: Promise<{ target: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return imageTargetPages.map((page) => ({ target: page.slug }));
}

export async function generateMetadata({ params }: TargetPageProps): Promise<Metadata> {
  const { target } = await params;
  const page = getImageTargetPage(target);
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
  const page = getImageTargetPage(target);
  if (!page) notFound();
  return <TargetSizePage page={page} />;
}
