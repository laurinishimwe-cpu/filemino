"use client";

import Link from "next/link";
import Image from "next/image";
import { useState } from "react";
import { Container } from "@/components/ui";

const links = [{ href: "/#tools", label: "Tools" }, { href: "/about", label: "About" }];

export function Header() {
  const [open, setOpen] = useState(false);
  return <header className="app-header"><Container><div className="app-header-inner"><Link className="app-logo" href="/"><Image className="app-logo-symbol" src="/FileMino-logo.svg" alt="" aria-hidden="true" width={32} height={32} priority /><span>FileMino</span></Link><nav className="app-nav" aria-label="Primary navigation">{links.map((link) => <Link className="app-nav-link" href={link.href} key={link.href}>{link.label}</Link>)}</nav><button className="ui-button ui-button-ghost app-mobile-toggle" type="button" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen((value) => !value)}>
          <span className="app-mobile-toggle-icon" aria-hidden="true">
            {open ? "✕" : "☰"}
          </span>
        </button></div><nav id="mobile-navigation" className="app-mobile-nav" data-open={open} aria-label="Mobile navigation">{links.map((link) => <Link className="app-nav-link" href={link.href} key={link.href} onClick={() => setOpen(false)}>{link.label}</Link>)}</nav></Container></header>;
}
