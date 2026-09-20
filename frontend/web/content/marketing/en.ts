import type { MarketingContent } from "./types";

/** The only locale shipped so far (ADR 0019) — Thai/Indonesian/Spanish are
 * additive files against `./types.ts`'s shape, not a rewrite, once there's
 * a real translation to put in them. Don't hand-wave numbers in here that
 * go stale (voice/model counts, job counts) — say things that stay true
 * regardless of catalog changes; the one place real live numbers belong is
 * the homepage gallery strip, which pulls them from `GET /gallery` itself. */
export const en: MarketingContent = {
  locale: "en",
  site: {
    name: "Voicica",
    tagline: "AI voice, image, and video — without the API key.",
    description:
      "Voicica turns natural-language prompts into speech, images, and video, using the same AI providers developers use — Azure, Google, Fish Audio, and Kie's model catalog — packaged into one fast, no-setup product.",
  },
  nav: [
    { label: "Voice", href: "/voice" },
    { label: "Image", href: "/image" },
    { label: "Video", href: "/video" },
  ],
  home: {
    metaTitle: "Voicica — AI Voice, Image & Video Generation",
    metaDescription:
      "Generate natural speech, clone your own voice, and create images and video from a prompt. No API keys, no setup — sign up and start creating in seconds.",
    hero: {
      title: "Turn a prompt into a voice, an image, or a video.",
      subtitle:
        "One account, no API keys. Natural text-to-speech in dozens of languages, your own cloned voice, and AI image/video generation — all in one place.",
      primaryCta: "Get started free",
      secondaryCta: "See what people are making",
    },
    capabilities: [
      {
        title: "Voice",
        description:
          "Natural-sounding text-to-speech across dozens of languages, plus clone your own voice once and reuse it forever.",
        href: "/voice",
      },
      {
        title: "Image",
        description: "Generate original images from a text prompt, or transform an existing photo into something new.",
        href: "/image",
      },
      {
        title: "Video",
        description: "Turn a reference image and a prompt into a short AI-generated video clip.",
        href: "/video",
      },
    ],
    galleryStrip: {
      title: "Made with Voicica",
      subtitle: "A live look at what people are creating right now — every one of these is a real, unedited result.",
      emptyText: "Nothing public yet — be the first.",
      ctaText: "Create your own",
    },
    cta: {
      title: "Free credits to start, no card required.",
      subtitle: "Create an account and get credits on the house — enough to try voice, image, and video generation yourself.",
      buttonText: "Sign up free",
    },
  },
  voice: {
    name: "Voice",
    metaTitle: "AI Text-to-Speech & Voice Cloning — Voicica",
    metaDescription:
      "Natural text-to-speech in dozens of languages from Azure and Google, plus clone your own voice once and generate unlimited speech in it.",
    hero: {
      title: "Text-to-speech that actually sounds natural — plus your own cloned voice.",
      subtitle:
        "Pick from a large catalog of natural voices across dozens of languages, fine-tune speed/pitch/volume, or train a voice model from a short recording of your own voice and reuse it forever.",
    },
    features: [
      {
        title: "A real voice catalog, not a handful of presets",
        description:
          "Voices from both Azure and Google, spanning dozens of languages and regional accents — not a narrow default list.",
      },
      {
        title: "Clone your own voice",
        description:
          "Record or upload a short sample once. Your cloned voice becomes a reusable asset you can generate new speech in, any time — the sample itself isn't kept after training.",
      },
      {
        title: "Fine control",
        description: "Adjust speed, pitch, and volume per generation, not just a single fixed setting.",
      },
      {
        title: "Fast, and billed only for what finishes",
        description: "Generation typically completes in seconds. A failed or rejected generation is never charged.",
      },
    ],
    howItWorks: {
      title: "How it works",
      steps: [
        "Type or paste the text you want spoken.",
        "Pick a voice from the catalog, or your own cloned voice.",
        "Generate — most speech is ready in seconds.",
      ],
    },
    cta: { title: "Try it with your own text.", buttonText: "Generate speech" },
  },
  image: {
    name: "Image",
    metaTitle: "AI Image Generation — Text-to-Image & Image-to-Image — Voicica",
    metaDescription:
      "Generate original images from a text prompt, or transform an existing photo — powered by Kie's curated model catalog (Flux, GPT Image, and more).",
    hero: {
      title: "Describe it, or reshape a photo you already have.",
      subtitle:
        "Generate original images from a text prompt (text-to-image), or give the model a reference photo and describe what should change (image-to-image).",
    },
    features: [
      {
        title: "Multiple models, one interface",
        description:
          "Choose between different image models depending on what you're after — speed, quality, or a specific style — without learning a new tool for each one.",
      },
      {
        title: "Bring your own reference photo",
        description: "Upload a photo and describe the change — a new background, an added detail, a different style.",
      },
      {
        title: "Real, per-model pricing",
        description: "Each model shows its exact cost before you generate — no surprise charges, and nothing is charged if a generation fails.",
      },
    ],
    howItWorks: {
      title: "How it works",
      steps: [
        "Pick a model from the catalog.",
        "Describe what you want (and upload a reference photo, for image-to-image).",
        "Generate — you'll see the real cost before you confirm.",
      ],
    },
    cta: { title: "Turn a prompt into an image.", buttonText: "Generate an image" },
  },
  video: {
    name: "Video",
    metaTitle: "AI Video Generation — Image-to-Video — Voicica",
    metaDescription:
      "Turn a reference image and a prompt into a short AI-generated video clip, with real per-second pricing shown before you generate.",
    hero: {
      title: "Bring a still image to life.",
      subtitle: "Give it a reference image and describe the motion or scene you want — get back a short AI-generated video clip.",
    },
    features: [
      {
        title: "Reference-image driven",
        description: "Start from a photo or a generated image, not a blank prompt — the output stays grounded in what you gave it.",
      },
      {
        title: "Control duration and resolution",
        description: "Pick clip length and resolution; the cost scales with what you choose and is shown before you generate.",
      },
      {
        title: "No charge on failure",
        description: "Video generation can take longer than other capabilities — you're notified the moment it's done, and never charged if it fails.",
      },
    ],
    howItWorks: {
      title: "How it works",
      steps: [
        "Upload a reference image.",
        "Describe the motion, scene, or style you want.",
        "Generate — you'll get a notification the moment your video is ready.",
      ],
    },
    cta: { title: "Turn an image into a video.", buttonText: "Generate a video" },
  },
  contact: {
    metaTitle: "Contact — Voicica",
    metaDescription: "How to reach the team behind Voicica.",
    title: "Contact",
    intro: "Voicica is operated by the individual listed below. For support, business, or partnership inquiries, reach out by email.",
    nameLabel: "Operator",
    name: "Sai Aung Tint",
    emailLabel: "Email",
    email: "bensting19@gmail.com",
    addressLabel: "Address",
    address: "Hasu Haus, Sukhumvit 77, Phra Khanong Nuea, Watthana, Bangkok 10110, Thailand",
    addressNote: "",
  },
  legal: {
    privacy: {
      title: "Privacy Policy",
      metaDescription: "How Voicica collects, uses, and protects your data.",
      updated: "September 14, 2026",
      intro:
        "This Privacy Policy explains what information Voicica (\"we\", \"us\") collects when you use the service, how it's used, and who it's shared with. This is a drafted starting point covering how the product actually works today, not a substitute for professional legal review.",
      sections: [
        {
          heading: "Information we collect",
          body: [
            "Account information: your email address and authentication details, handled by Firebase Authentication (a Google service). If you sign in with Google, we receive the basic profile information Google provides.",
            "Content you submit: text you enter for speech generation, prompts and reference images you submit for image/video generation, and voice samples you provide to train a cloned voice.",
            "Generated output: the audio, images, and video the service produces from your requests.",
            "Usage and billing data: which capabilities you use, credit balance and transaction history, and basic technical logs (timestamps, error states) needed to operate and troubleshoot the service.",
          ],
        },
        {
          heading: "How your content is processed",
          body: [
            "Generating a result means your text, prompt, or reference image is sent to the relevant third-party AI provider for that request — Microsoft Azure or Google Cloud (text-to-speech), Fish Audio (text-to-speech and voice cloning), or Kie.ai (image and video generation). Each provider processes that specific request; we don't control their internal retention beyond what their own terms specify.",
            "Voice cloning: the audio sample you provide is used once, to train a voice model with our voice-cloning provider. The sample itself is not stored by us after training completes — only a reference to the resulting reusable voice model is kept.",
            "Generated assets (audio, images, video) are copied to our own storage (Cloudflare R2) so you can access your history, and are kept for a limited retention period (currently 90 days), after which they are deleted.",
          ],
        },
        {
          heading: "How we use your information",
          body: [
            "To provide the service: authenticate you, process generation requests, maintain your credit balance and history, and show your past creations.",
            "To operate and improve the service: troubleshooting, abuse prevention, and understanding aggregate usage patterns.",
            "We do not sell your personal information.",
          ],
        },
        {
          heading: "What's public",
          body: [
            "By default, your creations are private: they are not listed in the public gallery or shown to other users. To keep things fast, the files themselves are served from unlisted web addresses that are long and effectively impossible to guess — but anyone who has a direct link to a file can open it, so only share links with people you trust.",
            "You may choose to mark a specific creation as public, which lists it in the public gallery for anyone to see, including people who aren't signed in — without revealing your identity, email, or account details alongside it. Marking it private again removes it from the gallery, but cannot revoke a link that was already shared; the file is deleted when its retention period ends.",
          ],
        },
        {
          heading: "Data retention and deletion",
          body: [
            "Generated assets are retained for a limited period and may be deleted afterward. Account and billing records are kept as needed to operate the service and meet legal obligations.",
            "To request deletion of your account or data, contact us using the details on the Contact page.",
          ],
        },
        {
          heading: "Changes to this policy",
          body: ["We may update this policy as the service changes. Material changes will be reflected here with an updated date."],
        },
      ],
    },
    terms: {
      title: "Terms & Conditions",
      metaDescription: "The terms that govern use of Voicica.",
      updated: "September 14, 2026",
      intro:
        "These Terms & Conditions govern your use of Voicica. By creating an account or using the service, you agree to them. This is a drafted starting point, not a substitute for professional legal review.",
      sections: [
        {
          heading: "The service",
          body: [
            "Voicica lets you generate speech, images, and video from prompts and reference content you provide, using third-party AI providers, packaged behind one account and one credit balance.",
            "Every capability requires a signed-in account. There is no anonymous usage.",
          ],
        },
        {
          heading: "Credits and billing",
          body: [
            "Generation is paid for with credits. New accounts receive a signup bonus of credits with no cash value, at our discretion, subject to change.",
            "The estimated cost of a generation is shown before you submit it. If a generation fails, you are not charged for it, and any held credits are released in full.",
            "We do not currently process direct payments; a paid top-up option will be described here once available, with these Terms updated accordingly.",
            "Credits are non-refundable except where required by applicable law.",
          ],
        },
        {
          heading: "Acceptable use",
          body: [
            "You're responsible for the content you submit and generate. You may not use Voicica to:",
            "• Clone or generate a voice, image, or likeness of a real person without their consent.",
            "• Generate content that is illegal, infringes someone else's rights, or is intended to deceive, defame, or harass.",
            "• Attempt to circumvent credit limits, rate limits, or other technical protections of the service.",
            "We may suspend or terminate accounts that violate these terms.",
          ],
        },
        {
          heading: "Your content and generated output",
          body: [
            "You retain ownership of the prompts, text, images, and audio samples you submit. Subject to your compliance with these Terms, you may use the content Voicica generates for you, including commercially.",
            "Underlying AI models are provided by third parties; we don't guarantee that generated output is free of third-party rights or that it's suitable for every purpose — you're responsible for reviewing output before relying on it.",
          ],
        },
        {
          heading: "Availability",
          body: [
            "Voicica depends on third-party AI providers (Azure, Google, Fish Audio, Kie) and infrastructure (Firebase, Neon, Cloudflare, Upstash). We aim for reliable service but don't guarantee uninterrupted availability, and are not responsible for outages caused by a third-party provider.",
          ],
        },
        {
          heading: "Changes and termination",
          body: [
            "We may update these Terms as the service changes; continued use after an update means you accept the revised Terms. You may stop using the service and request account deletion at any time via the Contact page.",
          ],
        },
        {
          heading: "Governing law",
          body: [
            "These Terms are governed by the laws of Thailand, without regard to conflict-of-law principles, pending a full legal review as the business grows.",
          ],
        },
      ],
    },
  },
  footer: {
    tagline: "AI voice, image, and video generation.",
    copyright: `© ${new Date().getFullYear()} Voicica. All rights reserved.`,
  },
};
