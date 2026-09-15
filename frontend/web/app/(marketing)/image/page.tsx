import type { Metadata } from "next";
import { en as content } from "@/content/marketing/en";
import { buildMarketingAlternates, buildMarketingUrl } from "@/lib/marketing-seo";
import { CapabilityPage } from "@/components/marketing/CapabilityPage";

export const metadata: Metadata = {
  title: content.image.metaTitle,
  description: content.image.metaDescription,
  alternates: { canonical: buildMarketingUrl("", "image"), languages: buildMarketingAlternates("image") },
  openGraph: {
    title: content.image.metaTitle,
    description: content.image.metaDescription,
    url: buildMarketingUrl("", "image"),
    siteName: content.site.name,
    type: "website",
  },
};

export default function ImagePage() {
  return <CapabilityPage content={content.image} />;
}
