"use client";

import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/cn";

type AutoScrollRegionProps = {
  active: boolean;
  children: ReactNode;
  className?: string;
};

export function AutoScrollRegion({ active, children, className }: AutoScrollRegionProps) {
  const regionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!active) return;

    const frame = window.requestAnimationFrame(() => {
      const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
      regionRef.current?.scrollIntoView({ behavior, block: "start" });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [active]);

  return <div ref={regionRef} className={cn("auto-scroll-region", className)}>{children}</div>;
}
