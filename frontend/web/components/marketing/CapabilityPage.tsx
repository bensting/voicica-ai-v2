import Link from "next/link";
import type { CapabilityPageContent } from "@/content/marketing/types";

/** Shared shell for `/voice`, `/image`, `/video` — same hero → features →
 * how-it-works → CTA shape (the old project's own SEO-page pattern,
 * ADR 0019), parameterized by content so the three pages are each just a
 * `content/marketing/en.ts` slice plus a route, not three copies of this
 * layout. */
export function CapabilityPage({ content }: { content: CapabilityPageContent }) {
  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-[10%] -right-[10%] w-[55%] h-[30%] rounded-full bg-a2/12 blur-[100px]" />
      </div>

      <section className="relative px-5 pb-8 pt-20 sm:px-8 md:pb-12 md:pt-28">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="font-display text-3xl font-bold md:text-5xl">{content.hero.title}</h1>
          <p className="mx-auto mt-4 max-w-xl text-base text-text-2 md:text-lg">{content.hero.subtitle}</p>
          <Link
            href="/login"
            className="grad-bg mt-7 inline-block rounded-2xl px-6 py-3.5 text-sm font-semibold text-[#120a1c]"
          >
            {content.cta.buttonText}
          </Link>
        </div>
      </section>

      <section className="relative px-5 py-12 sm:px-8 md:py-20">
        <div className="mx-auto grid max-w-5xl gap-5 md:grid-cols-2">
          {content.features.map((feature) => (
            <div key={feature.title} className="rounded-2xl border border-border-soft bg-surface p-6">
              <h2 className="font-display text-base font-bold">{feature.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-text-2">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="relative px-5 py-12 sm:px-8 md:py-20">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-center font-display text-2xl font-bold">{content.howItWorks.title}</h2>
          <ol className="mt-8 flex flex-col gap-5">
            {content.howItWorks.steps.map((step, i) => (
              <li key={step} className="flex items-start gap-4">
                <span className="grad-bg flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-[#120a1c]">
                  {i + 1}
                </span>
                <p className="pt-0.5 text-sm text-text-2">{step}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="relative px-5 py-16 sm:px-8 md:py-24">
        <div className="mx-auto max-w-2xl rounded-3xl border border-border-soft bg-surface p-10 text-center">
          <h2 className="font-display text-2xl font-bold">{content.cta.title}</h2>
          <Link
            href="/login"
            className="grad-bg mt-6 inline-block rounded-2xl px-6 py-3.5 text-sm font-semibold text-[#120a1c]"
          >
            {content.cta.buttonText}
          </Link>
        </div>
      </section>
    </div>
  );
}
