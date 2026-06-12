import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Xeno CRM — AI-Powered Campaign Manager",
  description:
    "Chat-to-Campaign CRM: Use natural language to segment customers, draft personalized messages, and launch campaigns with real-time delivery tracking.",
  keywords: ["CRM", "AI", "campaign management", "customer segmentation", "marketing automation"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
