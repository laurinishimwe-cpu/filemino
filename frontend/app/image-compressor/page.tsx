import type { Metadata } from "next";
import { ApplicationShell } from "@/components/layout";
import { ImageCompressor } from "@/components/tools/image-compressor/ImageCompressor";

export const metadata: Metadata = {
  title: "Compress Images Online | FluxFile",
  description: "Compress JPG, PNG, and WebP images with configurable quality, target size, output format, and dimensions.",
  alternates: { canonical: "/image-compressor" },
};

export default function ImageCompressorPage() {
  return <ApplicationShell><ImageCompressor /></ApplicationShell>;
}
