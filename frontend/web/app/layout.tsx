import type { Metadata } from "next";
import { Bricolage_Grotesque, Hanken_Grotesk } from "next/font/google";
import { AuthProvider } from "@/lib/auth-context";
import "./globals.css";

const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const hanken = Hanken_Grotesk({
  variable: "--font-hanken",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Voicica",
  // Kept in sync with what's actually shipped (content/marketing/en.ts,
  // ADR 0019) — music generation has no models catalogued yet, don't
  // advertise it here just because the old project's copy did.
  description: "AI voice, image, and video generation.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${bricolage.variable} ${hanken.variable} h-full`}>
      <body className="min-h-full font-sans antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
