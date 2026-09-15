import type { Metadata } from "next";
import { headers } from "next/headers";
import { GalleryStrip } from "@/components/marketing/GalleryStrip";
import { isAndroidUserAgent } from "@/lib/device";
import { buildMarketingUrl } from "@/lib/marketing-seo";
import { ConversionCtas } from "./ConversionCtas";

/** `robots: {index: false}` (ADR 0021) — this page exists for paid/campaign
 * traffic that already arrives with a destination in mind, not for organic
 * search to surface; indexing it alongside the homepage's near-identical
 * pitch would just be duplicate content. `follow: true` and no
 * `robots.txt` disallow, deliberately: ad platforms' own review crawlers
 * (Google/Meta ad quality checks) still need to fetch this page normally. */
export const metadata: Metadata = {
  title: "Get Voicica — AI Voice, Image & Video",
  description: "Generate voices, images, and videos with AI. Free to start, on the web or on Android.",
  alternates: { canonical: buildMarketingUrl("", "get") },
  robots: { index: false, follow: true },
};

const CAPABILITIES = [
  { label: "Voice", description: "Natural text-to-speech, or clone your own voice." },
  { label: "Image", description: "Generate images from a prompt, or transform a photo." },
  { label: "Video", description: "Bring a still image to life." },
];

export default async function GetPage() {
  const headersList = await headers();
  const isAndroid = isAndroidUserAgent(headersList.get("user-agent"));

  return (
    <div>
      <section className="px-5 pb-10 pt-6 sm:px-8 md:pb-16">
        <div className="mx-auto max-w-xl text-center">
          <h1 className="font-display text-3xl font-bold md:text-5xl">
            Your voice, image, and video generator.
          </h1>
          <p className="mx-auto mt-4 max-w-md text-base text-text-2">
            One account, no API keys. Free credits to start — on the web right now, or as a real
            Android app.
          </p>
          <div className="mt-8">
            <ConversionCtas isAndroid={isAndroid} />
          </div>
        </div>
      </section>

      <GalleryStrip />

      <section className="px-5 pb-16 sm:px-8 md:pb-24">
        <div className="mx-auto grid max-w-3xl gap-4 sm:grid-cols-3">
          {CAPABILITIES.map((c) => (
            <div key={c.label} className="rounded-2xl border border-border-soft bg-surface p-5 text-center">
              <div className="font-display font-bold">{c.label}</div>
              <p className="mt-1.5 text-sm text-text-2">{c.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="px-5 pb-20 sm:px-8">
        <div className="mx-auto max-w-xl text-center">
          <ConversionCtas isAndroid={isAndroid} />
        </div>
      </section>
    </div>
  );
}
