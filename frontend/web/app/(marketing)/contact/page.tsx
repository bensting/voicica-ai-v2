import type { Metadata } from "next";
import { en as content } from "@/content/marketing/en";
import { buildMarketingAlternates, buildMarketingUrl } from "@/lib/marketing-seo";

export const metadata: Metadata = {
  title: content.contact.metaTitle,
  description: content.contact.metaDescription,
  alternates: { canonical: buildMarketingUrl("", "contact"), languages: buildMarketingAlternates("contact") },
};

/** Exists as its own page, not folded into the footer, specifically to
 * satisfy a payment processor's website-verification checklist (at least
 * two of: full name, company-domain email, phone, email, an address
 * matching the account's profile, a photo) — ADR 0019. The address row is
 * deliberately real and public for now; the intent is to remove/hide it
 * once verification clears (manual follow-up, not automated here). */
export default function ContactPage() {
  const c = content.contact;
  return (
    <div className="px-5 py-20 sm:px-8">
      <div className="mx-auto max-w-lg">
        <h1 className="font-display text-3xl font-bold">{c.title}</h1>
        <p className="mt-3 text-sm text-text-2">{c.intro}</p>

        <dl className="mt-8 flex flex-col gap-5 rounded-2xl border border-border-soft bg-surface p-6">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-text-3">{c.nameLabel}</dt>
            <dd className="mt-1 text-sm">{c.name}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-text-3">{c.emailLabel}</dt>
            <dd className="mt-1 text-sm">
              <a href={`mailto:${c.email}`} className="text-a3 hover:underline">
                {c.email}
              </a>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-text-3">{c.addressLabel}</dt>
            <dd className="mt-1 text-sm">{c.address}</dd>
            {c.addressNote && <dd className="mt-1 text-xs text-text-3">{c.addressNote}</dd>}
          </div>
        </dl>
      </div>
    </div>
  );
}
