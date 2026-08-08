"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronIcon } from "@/components/icons/ChevronIcon";
import { FileToolIcon } from "@/components/icons/files/FileToolIcon";
import type { ToolDefinition } from "@/lib/tools";
import { cn } from "@/lib/cn";

type ToolCardProps = { tool: ToolDefinition };

export function ToolCard({ tool }: ToolCardProps) {
  const pathname = usePathname();
  const active = Boolean(tool.href && pathname === tool.href);

  const content = (
    <>
      <span className="tool-card-icon">
        <FileToolIcon name={tool.icon} />
      </span>
      <span className="tool-card-body">
        <span className="tool-card-name">{tool.name}</span>
        {!tool.href && <span className="tool-card-status">Soon</span>}
      </span>
      {tool.href && (
        <span className="tool-card-nav" aria-hidden="true">
          <ChevronIcon />
        </span>
      )}
    </>
  );

  if (tool.href) {
    return (
      <Link
        className={cn("tool-card", active && "tool-card-active")}
        href={tool.href}
        aria-label={`Open ${tool.name}`}
        aria-current={active ? "page" : undefined}
      >
        {content}
      </Link>
    );
  }

  return (
    <div className="tool-card" data-unavailable="true" aria-disabled="true">
      {content}
    </div>
  );
}
