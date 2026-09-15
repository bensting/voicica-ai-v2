import type { Metadata } from "next";
import Link from "next/link";
import { en as content } from "@/content/marketing/en";
import { buildMarketingAlternates, buildMarketingUrl } from "@/lib/marketing-seo";
import { GalleryStrip } from "@/components/marketing/GalleryStrip";

export const metadata: Metadata = {
  title: content.home.metaTitle,
  description: content.home.metaDescription,
  alternates: { canonical: buildMarketingUrl(""), languages: buildMarketingAlternates() },
  openGraph: {
    title: content.home.metaTitle,
    description: content.home.metaDescription,
    url: buildMarketingUrl(""),
    siteName: content.site.name,
    type: "website",
  },
};

export default function HomePage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: content.site.name,
    url: buildMarketingUrl(""),
    applicationCategory: "MultimediaApplication",
    operatingSystem: "Web",
    description: content.site.description,
  };

  return (
    <div className="relative overflow-hidden">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-[10%] -left-[10%] w-[60%] h-[34%] rounded-full bg-a1/15 blur-[100px]" />
        <div className="absolute top-[10%] -right-[14%] w-[55%] h-[30%] rounded-full bg-a4/10 blur-[100px]" />
      </div>

      {/* Hero */}
      <section className="relative px-5 pb-10 pt-20 sm:px-8 md:pb-16 md:pt-28">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="font-display text-4xl font-bold md:text-6xl">{content.home.hero.title}</h1>
          <p className="mx-auto mt-5 max-w-xl text-base text-text-2 md:text-lg">{content.home.hero.subtitle}</p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/login" className="grad-bg rounded-2xl px-6 py-3.5 text-sm font-semibold text-[#120a1c]">
              {content.home.hero.primaryCta}
            </Link>
            <a href="#gallery" className="rounded-2xl border border-border-soft px-6 py-3.5 text-sm font-medium">
              {content.home.hero.secondaryCta}
            </a>
          </div>
        </div>
      </section>

      {/* Capabilities */}
      <section className="relative px-5 py-12 sm:px-8 md:py-20">
        <div className="mx-auto grid max-w-6xl gap-4 md:grid-cols-3">
          {content.home.capabilities.map((cap) => (
            <Link
              key={cap.href}
              href={cap.href}
              className="rounded-2xl border border-border-soft bg-surface p-6 transition-colors hover:border-a3/40"
            >
              <h2 className="font-display text-lg font-bold">{cap.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-text-2">{cap.description}</p>
              <span className="mt-4 inline-block text-sm font-semibold text-a3">Explore →</span>
            </Link>
          ))}
        </div>
      </section>

      <div id="gallery">
        <GalleryStrip />
      </div>

      {/* Final CTA */}
      <section className="relative px-5 py-16 sm:px-8 md:py-24">
        <div className="mx-auto max-w-2xl rounded-3xl border border-border-soft bg-surface p-10 text-center">
          <h2 className="font-display text-2xl font-bold md:text-3xl">{content.home.cta.title}</h2>
          <p className="mx-auto mt-3 max-w-md text-sm text-text-2">{content.home.cta.subtitle}</p>
          <Link
            href="/login"
            className="grad-bg mt-6 inline-block rounded-2xl px-6 py-3.5 text-sm font-semibold text-[#120a1c]"
          >
            {content.home.cta.buttonText}
          </Link>
        </div>
      </section>
    </div>
  );
}
