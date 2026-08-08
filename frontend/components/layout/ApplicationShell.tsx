import type { ReactNode } from "react";
import { Footer } from "./Footer";
import { Header } from "./Header";

export function ApplicationShell({ children }: { children: ReactNode }) {
  return <div className="app-shell"><Header /><main className="app-main">{children}</main><Footer /></div>;
}
