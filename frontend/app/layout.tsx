import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { getSiteUrl } from "@/lib/site-url";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: getSiteUrl(),
  title: { default: "FluxFile – Fast Online File Tools", template: "%s | FluxFile" },
  description: "Fast online tools for everyday files.",
  applicationName: "FluxFile",
  robots: { index: true, follow: true },
  openGraph: { type: "website", siteName: "FluxFile", title: "FluxFile", description: "Fast online tools for everyday files." },
  twitter: { card: "summary", title: "FluxFile", description: "Fast online tools for everyday files." },
  icons: { icon: "/FluxFile-logo.svg" },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
