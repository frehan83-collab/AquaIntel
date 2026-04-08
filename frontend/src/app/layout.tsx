import type { Metadata, Viewport } from "next";
import { DM_Serif_Display, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import { ToastProvider } from "@/components/Toast";
import PWARegister from "@/components/PWARegister";
import OfflineIndicator from "@/components/OfflineIndicator";
import DemoShell from "@/components/DemoShell";
import ErrorBoundary from "@/components/ErrorBoundary";
import DataAttribution from "@/components/DataAttribution";
import KeyboardShortcuts from "@/components/KeyboardShortcuts";
import GlobalErrorHandler from "@/components/GlobalErrorHandler";

const dmSerif = DM_Serif_Display({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FishIntel — Aquaculture Intelligence",
  description: "The world's most advanced salmon market intelligence platform — fishintel.io",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#0a0e1a",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
      </head>
      <body className={`${dmSerif.variable} ${dmSans.variable} ${jetbrainsMono.variable} font-sans antialiased bg-slate-50 dark:bg-ocean-950`}>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:top-4 focus:left-4 focus:px-4 focus:py-2 focus:bg-salmon focus:text-white focus:rounded-lg focus:text-sm focus:font-semibold focus:shadow-lg"
        >
          Skip to main content
        </a>
        <PWARegister />
        <OfflineIndicator />
        <GlobalErrorHandler />
        <ToastProvider>
          <KeyboardShortcuts />
          <Sidebar />
          <div className="md:ml-[240px] min-h-screen flex flex-col">
            <DemoShell />
            <TopBar />
            <main id="main-content" className="flex-1 p-6">
              <ErrorBoundary>{children}</ErrorBoundary>
            </main>
            <DataAttribution />
          </div>
        </ToastProvider>
      </body>
    </html>
  );
}
