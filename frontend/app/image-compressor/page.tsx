import type { Metadata } from "next";
import { ApplicationShell } from "@/components/layout";
import { ImageCompressor } from "@/components/tools/image-compressor/ImageCompressor";
import { ToolSeoContent } from "@/components/seo/ToolSeoContent";

export const metadata: Metadata = {
  title: "Compress Images Online | FluxFile",
  description: "Compress JPG, PNG, and WebP images with configurable quality, target size, output format, and dimensions.",
  alternates: { canonical: "/image-compressor" },
};

export default function ImageCompressorPage() {
  return <ApplicationShell><ImageCompressor /><ToolSeoContent title="Compress images with control" intro="Choose a simple compression goal or set a target file size. FluxFile can keep the original format or use a compatible output format when you choose it." steps={["Choose a JPG, PNG, or WebP image", "Pick Best Quality, Balanced, Smallest, or Target Size", "Adjust format or dimensions only when needed", "Download the result"]} points={["Target sizes aim for the highest practical quality at or below your chosen limit", "PNG, JPG, and WebP are supported", "No account is required", "Files are processed temporarily according to the configured retention policy"]} links={[{ href: "/compress-image-to-50kb", label: "Compress an image to 50 KB" }, { href: "/image-converter", label: "Convert image formats" }]} /></ApplicationShell>;
}
