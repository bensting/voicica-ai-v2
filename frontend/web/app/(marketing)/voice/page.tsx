import type { Metadata } from "next";
import { en as content } from "@/content/marketing/en";
import { buildMarketingAlternates, buildMarketingUrl } from "@/lib/marketing-seo";
import { CapabilityPage } from "@/components/marketing/CapabilityPage";

export const metadata: Metadata = {
  title: content.voice.metaTitle,
  description: content.voice.metaDescription,
  alternates: { canonical: buildMarketingUrl("", "voice"), languages: buildMarketingAlternates("voice") },
  openGraph: {
    title: content.voice.metaTitle,
    description: content.voice.metaDescription,
    url: buildMarketingUrl("", "voice"),
    siteName: content.site.name,
    type: "website",
  },
};

export default function VoicePage() {
  return <CapabilityPage content={content.voice} />;
}
