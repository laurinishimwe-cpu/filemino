import type { SVGProps } from "react";

export type FileToolIconName = "video" | "image" | "transparent-image" | "audio" | "convert" | "compress";

type FileToolIconProps = SVGProps<SVGSVGElement> & { name: FileToolIconName };

const documentPath = "M5.4 2.5h8.25L19 7.85v11.75a1.9 1.9 0 0 1-1.9 1.9H5.4a1.9 1.9 0 0 1-1.9-1.9V4.4a1.9 1.9 0 0 1 1.9-1.9Z";
const glyphStroke = { stroke: "var(--color-on-primary)", strokeWidth: 1.65, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export function FileToolIcon({ name, ...props }: FileToolIconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
      <path d={documentPath} fill="currentColor" />
      <path d="M13.65 2.5v4.2a1.15 1.15 0 0 0 1.15 1.15H19" fill="var(--color-primary-muted)" />

      {name === "video" && <><circle cx="11.25" cy="14.35" r="4" {...glyphStroke} /><path d="m10.35 12.7 2.55 1.65-2.55 1.65V12.7Z" fill="var(--color-on-primary)" stroke="none" /></>}
      {name === "image" && <><rect x="7.2" y="10.35" width="8.1" height="7.1" rx="1.1" {...glyphStroke} /><circle cx="9.45" cy="12.55" r=".8" fill="var(--color-on-primary)" /><path d="m8.25 16.05 2.05-2.05 1.5 1.4 1.35-1.25 1.1 1.1" {...glyphStroke} /></>}
      {name === "transparent-image" && <><rect x="7.2" y="10.35" width="8.1" height="7.1" rx="1.1" {...glyphStroke} /><path d="m8.25 16.05 2.05-2.05 1.5 1.4 1.35-1.25 1.1 1.1M7.2 18.3l9.6-9.6" {...glyphStroke} /></>}
      {name === "audio" && <><path d="M13.9 10.6v5.7M13.9 10.6l-4.1 1.15v4.25" {...glyphStroke} /><circle cx="8.5" cy="16.85" r="1.45" {...glyphStroke} /><circle cx="12.6" cy="16.1" r="1.45" {...glyphStroke} /></>}
      {name === "convert" && <><path d="M8 12h6.35M12.15 9.85 14.3 12l-2.15 2.15M16 16h-6.35M11.85 13.85 9.7 16l2.15 2.15" {...glyphStroke} /></>}
      {name === "compress" && <><path d="M8.65 12.2h5.7M10.1 14.55h2.8M10.1 9.85h2.8M11.5 8.25v6.1M9.75 9.95l1.75-1.7 1.75 1.7M9.75 12.65l1.75 1.7 1.75-1.7" {...glyphStroke} /></>}
    </svg>
  );
}
