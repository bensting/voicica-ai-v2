"use client";

import Image from "next/image";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { en as content } from "@/content/marketing/en";

/** The public, no-login surface (ADR 0005 §3, ADR 0019) — a plain header +
 * footer shell around whatever page renders inside it. Only the header/
 * footer chrome needs to be a client component (it reads auth state to
 * decide "Sign in" vs. "Go to app"); each page underneath stays a server
 * component so its actual content is still SSR'd for SEO. English-only
 * content for now (ADR 0019) — this reads `content/marketing/en` directly
 * rather than resolving a locale, since there's nothing else to resolve to
 * yet; a `[locale]` version of this file is the seam where that changes. */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <header className="border-b border-border-soft">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <Link href="/" className="flex items-center gap-2.5">
            <Image src="/brand/mark.webp" alt="" width={28} height={28} priority />
            <span className="font-display text-lg font-bold tracking-tight">{content.site.name}</span>
          </Link>

          <nav className="hidden items-center gap-7 md:flex">
            {content.nav.map((item) => (
              <Link key={item.href} href={item.href} className="text-sm font-medium text-text-2 hover:text-text">
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2.5">
            {user ? (
              <Link
                href="/app"
                className="grad-bg rounded-xl px-4 py-2 text-sm font-semibold text-[#120a1c]"
              >
                Go to app
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="hidden rounded-xl border border-border-soft px-4 py-2 text-sm font-medium text-text sm:block"
                >
                  Sign in
                </Link>
                <Link href="/login" className="grad-bg rounded-xl px-4 py-2 text-sm font-semibold text-[#120a1c]">
                  Get started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-border-soft">
        <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
          <div className="flex flex-col gap-8 sm:flex-row sm:justify-between">
            <div className="max-w-xs">
              <div className="flex items-center gap-2.5">
                <Image src="/brand/mark.webp" alt="" width={24} height={24} />
                <span className="font-display text-base font-bold tracking-tight">{content.site.name}</span>
              </div>
              <p className="mt-2.5 text-sm text-text-2">{content.footer.tagline}</p>
            </div>

            <div className="flex gap-14">
              <div className="flex flex-col gap-2.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-text-3">Product</span>
                {content.nav.map((item) => (
                  <Link key={item.href} href={item.href} className="text-sm text-text-2 hover:text-text">
                    {item.label}
                  </Link>
                ))}
              </div>
              <div className="flex flex-col gap-2.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-text-3">Legal</span>
                <Link href="/privacy" className="text-sm text-text-2 hover:text-text">
                  Privacy Policy
                </Link>
                <Link href="/terms" className="text-sm text-text-2 hover:text-text">
                  Terms &amp; Conditions
                </Link>
                <Link href="/contact" className="text-sm text-text-2 hover:text-text">
                  Contact
                </Link>
              </div>
            </div>
          </div>

          <p className="mt-10 text-xs text-text-3">{content.footer.copyright}</p>
        </div>
      </footer>
    </div>
  );
}
