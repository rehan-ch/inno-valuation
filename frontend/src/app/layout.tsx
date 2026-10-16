import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InnoValuation",
  description: "Innovation diagnostic platform.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-md focus:border focus:border-neutral-300 focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:text-neutral-900"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
