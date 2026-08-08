import type { ImageConversionOutputFormat } from "@/lib/api/types";

export type DetectedImageFormat = "PNG" | "JPEG" | "WEBP" | "ICO" | "BMP" | "TIFF";
export type ImageConversionCapability = { label: string; description: string; targets: ImageConversionOutputFormat[]; recommended: ImageConversionOutputFormat };

export const imageConversionCapabilities: Record<DetectedImageFormat, ImageConversionCapability> = {
  PNG: { label: "PNG", description: "Lossless + transparency", targets: ["jpeg", "webp", "ico"], recommended: "webp" },
  JPEG: { label: "JPG", description: "Photos + compatibility", targets: ["png", "webp", "ico"], recommended: "webp" },
  WEBP: { label: "WebP", description: "Small modern images", targets: ["png", "jpeg", "ico"], recommended: "png" },
  ICO: { label: "ICO", description: "App & website icons", targets: ["png", "jpeg", "webp"], recommended: "png" },
  BMP: { label: "BMP", description: "Bitmap image", targets: ["png", "jpeg", "webp"], recommended: "png" },
  TIFF: { label: "TIFF", description: "High-quality image", targets: ["png", "jpeg", "webp"], recommended: "png" },
};

export const imageConversionTargetDetails: Record<ImageConversionOutputFormat, { label: string; description: string }> = {
  png: { label: "PNG", description: "Lossless + transparency" },
  jpeg: { label: "JPG", description: "Photos + compatibility" },
  webp: { label: "WebP", description: "Small modern images" },
  ico: { label: "ICO", description: "App & website icons" },
};

export function preliminaryImageFormat(file: File): DetectedImageFormat | null {
  const extension = file.name.split(".").pop()?.toLowerCase();
  const formats: Record<string, DetectedImageFormat> = { png: "PNG", jpg: "JPEG", jpeg: "JPEG", webp: "WEBP", ico: "ICO", bmp: "BMP", tif: "TIFF", tiff: "TIFF" };
  return extension ? formats[extension] ?? null : null;
}
