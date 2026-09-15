import type { Metadata, Viewport } from "next";
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

// `viewportFit: "cover"` is the one that actually matters here: without it,
// `env(safe-area-inset-*)` reports 0 on every device (Safari/Chromium only
// expose a non-zero inset once the page opts into drawing under the
// notch/home-indicator area) — `BottomNav`'s `paddingBottom:
// env(safe-area-inset-bottom, 0px)` was silently a no-op the whole time
// without this, letting its content sit flush against a phone's home-
// indicator gesture area instead of clearing it.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
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
