import type { SVGProps } from "react";

type ChevronIconProps = SVGProps<SVGSVGElement> & { direction?: "left" | "right" };

export function ChevronIcon({ direction = "right", ...props }: ChevronIconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" {...props}>
      <path
        d={direction === "right" ? "M7.5 5l5 5-5 5" : "M12.5 5l-5 5 5 5"}
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
