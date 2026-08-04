import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "sonner";

import { BackgroundFx } from "@/components/chrome/background-fx";
import { SiteHeader } from "@/components/chrome/site-header";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  style: ["normal", "italic"],
  axes: ["opsz", "SOFT", "WONK"],
});

export const metadata: Metadata = {
  title: "Filing Reconciler — Cross-document contradiction analyst",
  description:
    "Ingests 10-Ks, 10-Qs, earnings calls and press releases, reconciles claims across documents, and drafts a cited, human-reviewed risk memo.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body className="relative min-h-full flex flex-col">
        <BackgroundFx />
        <SiteHeader />
        <main className="flex-1">{children}</main>
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: "var(--surface-raised)",
              border: "1px solid var(--border-subtle)",
              color: "var(--foreground)",
            },
          }}
        />
      </body>
    </html>
  );
}
