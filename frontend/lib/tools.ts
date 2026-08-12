import type { FileToolIconName } from "@/components/icons/files/FileToolIcon";

export type ToolDefinition = {
  name: string;
  icon: FileToolIconName;
  href?: string;
};

export const fileMinoTools: ToolDefinition[] = [
  { name: "Video Compressor", icon: "video", href: "/video-compressor" },
  { name: "Image Compressor", icon: "image", href: "/image-compressor" },
  { name: "Remove Background", icon: "transparent-image" },
  { name: "Video to MP3", icon: "audio" },
  { name: "Image Converter", icon: "convert", href: "/image-converter" },
  { name: "Video Converter", icon: "convert" },
];

export const relatedFileMinoTools = fileMinoTools.filter((tool) => tool.name !== "Video Compressor");
