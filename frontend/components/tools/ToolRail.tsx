"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronIcon } from "@/components/icons/ChevronIcon";
import { ToolCard } from "./ToolCard";
import type { ToolDefinition } from "@/lib/tools";

type ToolRailProps = { tools: ToolDefinition[]; label: string; compact?: boolean };

export function ToolRail({ tools, label, compact = false }: ToolRailProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const node = scrollRef.current;
    if (!node) return;

    const { scrollLeft, scrollWidth, clientWidth } = node;
    const overflow = scrollWidth - clientWidth > 4;
    setCanScrollLeft(overflow && scrollLeft > 4);
    setCanScrollRight(overflow && scrollLeft + clientWidth < scrollWidth - 4);
  }, []);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;

    updateScrollState();

    const observer = new ResizeObserver(updateScrollState);
    observer.observe(node);
    node.addEventListener("scroll", updateScrollState, { passive: true });

    return () => {
      observer.disconnect();
      node.removeEventListener("scroll", updateScrollState);
    };
  }, [updateScrollState, tools]);

  const scrollBy = (direction: "left" | "right") => {
    scrollRef.current?.scrollBy({
      left: direction === "left" ? -240 : 240,
      behavior: "smooth",
    });
  };

  return (
    <div
      className="tool-rail-wrap"
      data-compact={compact}
      data-can-scroll-left={canScrollLeft}
      data-can-scroll-right={canScrollRight}
    >
      {canScrollLeft && (
        <button
          type="button"
          className="tool-rail-nav tool-rail-nav-prev"
          aria-label="Scroll tools left"
          onClick={() => scrollBy("left")}
        >
          <ChevronIcon direction="left" />
        </button>
      )}

      <div className="tool-rail" ref={scrollRef} aria-label={label} role="list">
        {tools.map((tool) => (
          <ToolCard key={tool.name} tool={tool} />
        ))}
      </div>

      {canScrollRight && (
        <button
          type="button"
          className="tool-rail-nav tool-rail-nav-next"
          aria-label="Scroll tools right"
          onClick={() => scrollBy("right")}
        >
          <ChevronIcon direction="right" />
        </button>
      )}
    </div>
  );
}
