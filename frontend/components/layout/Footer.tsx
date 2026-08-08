import Link from "next/link";
import { Container } from "@/components/ui";

const links = [{ href: "/#tools", label: "Tools" }, { href: "/#about", label: "About" }, { href: "/#privacy", label: "Privacy" }, { href: "/#terms", label: "Terms" }];

export function Footer() {
  return <footer className="app-footer"><Container><div className="app-footer-inner"><p className="app-footer-brand">© {new Date().getFullYear()} FluxFile. Simple file tools.</p><nav className="app-footer-nav" aria-label="Footer navigation">{links.map((link) => <Link className="app-footer-link" href={link.href} key={link.href}>{link.label}</Link>)}</nav></div></Container></footer>;
}
