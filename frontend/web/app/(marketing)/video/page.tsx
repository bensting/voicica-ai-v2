import type { Metadata } from "next";
import { en as content } from "@/content/marketing/en";
import { buildMarketingAlternates, buildMarketingUrl } from "@/lib/marketing-seo";
import { CapabilityPage } from "@/components/marketing/CapabilityPage";

export const metadata: Metadata = {
  title: content.video.metaTitle,
  description: content.video.metaDescription,
  alternates: { canonical: buildMarketingUrl("", "video"), languages: buildMarketingAlternates("video") },
  openGraph: {
    title: content.video.metaTitle,
    description: content.video.metaDescription,
    url: buildMarketingUrl("", "video"),
    siteName: content.site.name,
    type: "website",
  },
};

export default function VideoPage() {
  return <CapabilityPage content={content.video} />;
}
