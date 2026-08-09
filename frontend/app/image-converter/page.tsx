import type { Metadata } from "next";
import { ApplicationShell } from "@/components/layout";
import { ImageConverter } from "@/components/tools/image-converter/ImageConverter";
import { ToolSeoContent } from "@/components/seo/ToolSeoContent";

export const metadata: Metadata = { title: "Image Converter Online | FluxFile", description: "Convert PNG, JPG, WebP, ICO, BMP, and TIFF images between popular formats.", alternates: { canonical: "/image-converter" } };
export default function ImageConverterPage() { return <ApplicationShell><ImageConverter /><ToolSeoContent title="Convert common image formats" intro="FluxFile detects the uploaded image format and presents compatible output choices, including practical ICO conversion." steps={["Choose an image", "Review the detected format", "Choose a compatible output format", "Download the converted image"]} points={["PNG, JPG, WebP, ICO, BMP, and TIFF input support", "Transparency is preserved where the selected format supports it", "ICO files can include multiple icon sizes", "No account is required"]} links={[{ href: "/png-to-webp", label: "Convert PNG to WebP" }, { href: "/png-to-jpg", label: "Convert PNG to JPG" }]} /></ApplicationShell>; }
