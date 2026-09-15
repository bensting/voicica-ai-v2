/** The shape every marketing locale file must fill in (ADR 0019). Kept as
 * plain data — not JSX — so adding a language later (`th.ts`, `id.ts`,
 * `es.ts`) is a translation task against this shape, not a rewrite of any
 * page component. Only `en.ts` exists today; see `registry.ts`. */

export interface LegalSection {
  heading: string;
  body: string[];
}

export interface CapabilityFeature {
  title: string;
  description: string;
}

export interface CapabilityPageContent {
  /** Used in <title>/<h1>/nav — keep short. */
  name: string;
  metaTitle: string;
  metaDescription: string;
  hero: { title: string; subtitle: string };
  features: CapabilityFeature[];
  howItWorks: { title: string; steps: string[] };
  cta: { title: string; buttonText: string };
}

export interface MarketingContent {
  locale: string;
  site: {
    name: string;
    tagline: string;
    /** Plain-language description reused in metadata + JSON-LD. */
    description: string;
  };
  nav: { label: string; href: string }[];
  home: {
    metaTitle: string;
    metaDescription: string;
    hero: { title: string; subtitle: string; primaryCta: string; secondaryCta: string };
    capabilities: { title: string; description: string; href: string }[];
    galleryStrip: { title: string; subtitle: string; emptyText: string; ctaText: string };
    cta: { title: string; subtitle: string; buttonText: string };
  };
  voice: CapabilityPageContent;
  image: CapabilityPageContent;
  video: CapabilityPageContent;
  contact: {
    metaTitle: string;
    metaDescription: string;
    title: string;
    intro: string;
    nameLabel: string;
    name: string;
    emailLabel: string;
    email: string;
    addressLabel: string;
    address: string;
    addressNote: string;
  };
  legal: {
    privacy: { title: string; metaDescription: string; updated: string; intro: string; sections: LegalSection[] };
    terms: { title: string; metaDescription: string; updated: string; intro: string; sections: LegalSection[] };
  };
  footer: {
    tagline: string;
    copyright: string;
  };
}
