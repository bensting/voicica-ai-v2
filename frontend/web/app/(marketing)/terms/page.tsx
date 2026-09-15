import type { Metadata } from "next";
import { en as content } from "@/content/marketing/en";
import { buildMarketingAlternates, buildMarketingUrl } from "@/lib/marketing-seo";
import { LegalPage } from "@/components/marketing/LegalPage";

export const metadata: Metadata = {
  title: content.legal.terms.title,
  description: content.legal.terms.metaDescription,
  alternates: { canonical: buildMarketingUrl("", "terms"), languages: buildMarketingAlternates("terms") },
};

export default function TermsPage() {
  const { title, updated, intro, sections } = content.legal.terms;
  return <LegalPage title={title} updated={updated} intro={intro} sections={sections} />;
}
