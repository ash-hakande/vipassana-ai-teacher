import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vipassana AI Assistant",
  description: "A grounded chat assistant for Vipassana teaching documents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
