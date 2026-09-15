import Image from "next/image";
import Link from "next/link";
import { Analytics } from "@/components/Analytics";

/** A dedicated conversion landing page (ADR 0021), deliberately outside
 * `(marketing)`'s layout — that one's header/footer link to `/voice`,
 * `/image`, `/video`, and the homepage itself, exactly the exits a page
 * meant to be the sole destination for paid/campaign traffic shouldn't
 * offer. The only two ways out of this page are the two real conversion
 * actions (`ConversionCtas`); even the logo here is a plain, non-clickable
 * mark, not a link back to `/`. Legal links (Privacy/Terms) stay in the
 * footer since they're an expected, not a distracting, presence. */
export default function GetLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <Analytics />

      <header className="px-5 py-6 sm:px-8">
        <div className="mx-auto flex max-w-3xl items-center gap-2.5">
          <Image src="/brand/mark.webp" alt="" width={26} height={26} />
          <span className="font-display text-base font-bold tracking-tight">Voicica</span>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="px-5 py-8 sm:px-8">
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-2 text-xs text-text-3 sm:flex-row sm:justify-between">
          <span>© {new Date().getFullYear()} Voicica. All rights reserved.</span>
          <div className="flex gap-4">
            <Link href="/privacy" className="hover:text-text-2">
              Privacy Policy
            </Link>
            <Link href="/terms" className="hover:text-text-2">
              Terms &amp; Conditions
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
