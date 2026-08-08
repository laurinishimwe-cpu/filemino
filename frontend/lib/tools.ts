import type { FileToolIconName } from "@/components/icons/files/FileToolIcon";

export type ToolDefinition = {
  name: string;
  icon: FileToolIconName;
  href?: string;
};

export const fluxFileTools: ToolDefinition[] = [
  { name: "Video Compressor", icon: "video", href: "/video-compressor" },
  { name: "Image Compressor", icon: "image" },
  { name: "Remove Background", icon: "transparent-image" },
  { name: "Video to MP3", icon: "audio" },
  { name: "Image Converter", icon: "convert" },
  { name: "Video Converter", icon: "convert" },
];

export const relatedFluxFileTools = fluxFileTools.filter((tool) => tool.name !== "Video Compressor");
