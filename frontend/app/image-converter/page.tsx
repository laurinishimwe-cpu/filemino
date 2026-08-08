import type { Metadata } from "next";
import { ApplicationShell } from "@/components/layout";
import { ImageConverter } from "@/components/tools/image-converter/ImageConverter";

export const metadata: Metadata = { title: "Image Converter Online | FluxFile", description: "Convert PNG, JPG, WebP, ICO, BMP, and TIFF images between popular formats.", alternates: { canonical: "/image-converter" } };
export default function ImageConverterPage() { return <ApplicationShell><ImageConverter /></ApplicationShell>; }
