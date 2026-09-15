import type { Metadata } from "next";
import { en as content } from "@/content/marketing/en";
import { buildMarketingAlternates, buildMarketingUrl } from "@/lib/marketing-seo";
import { LegalPage } from "@/components/marketing/LegalPage";

export const metadata: Metadata = {
  title: content.legal.privacy.title,
  description: content.legal.privacy.metaDescription,
  alternates: { canonical: buildMarketingUrl("", "privacy"), languages: buildMarketingAlternates("privacy") },
};

export default function PrivacyPage() {
  const { title, updated, intro, sections } = content.legal.privacy;
  return <LegalPage title={title} updated={updated} intro={intro} sections={sections} />;
}
