import type { ReactNode } from "react";
import { Footer } from "./Footer";
import { Header } from "./Header";
import { ToolBar } from "./ToolBar";

export function ApplicationShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <Header />
      <ToolBar />
      <main className="app-main">{children}</main>
      <Footer />
    </div>
  );
}
