import { ApplicationShell } from "@/components/layout";
import { VideoCompressor } from "@/components/tools/video-compressor/VideoCompressor";
import { ToolSeoContent } from "@/components/seo/ToolSeoContent";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Free Video Compressor – Compress Videos Online", description: "Compress videos up to 2 GB for free with no watermark. Choose quality and resolution, then download a smaller MP4.", alternates: { canonical: "/video-compressor" } };

export default function VideoCompressorPage() {
  return <ApplicationShell><VideoCompressor /><ToolSeoContent title="How video compression works" intro="Upload a supported video, choose a compression mode and optional resolution, then download the processed MP4." steps={["Choose a video file", "Select Best Quality, Balanced, or Smallest Size", "Optionally choose an output resolution", "Download the compressed video"]} points={["Compress videos up to 2 GB for free", "No watermark is added", "No account is required", "Files are kept in private storage and are subject to FileMino’s configured temporary retention policy"]} links={[{ href: "/image-compressor", label: "Compress images" }, { href: "/image-converter", label: "Convert images" }]} /></ApplicationShell>;
}
