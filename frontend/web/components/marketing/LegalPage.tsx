import type { LegalSection } from "@/content/marketing/types";

/** Shared renderer for `/privacy` and `/terms` — both are the same shape
 * (title, "last updated", intro paragraph, sections of heading + body
 * paragraphs), so the actual legal copy lives entirely in
 * `content/marketing/en.ts` and this file only knows how to lay it out. */
export function LegalPage({
  title,
  updated,
  intro,
  sections,
}: {
  title: string;
  updated: string;
  intro: string;
  sections: LegalSection[];
}) {
  return (
    <div className="px-5 py-20 sm:px-8">
      <div className="mx-auto max-w-2xl">
        <h1 className="font-display text-3xl font-bold">{title}</h1>
        <p className="mt-2 text-xs text-text-3">Last updated: {updated}</p>
        <p className="mt-6 text-sm leading-relaxed text-text-2">{intro}</p>

        <div className="mt-10 flex flex-col gap-8">
          {sections.map((section) => (
            <section key={section.heading}>
              <h2 className="font-display text-lg font-bold">{section.heading}</h2>
              <div className="mt-2.5 flex flex-col gap-2.5">
                {section.body.map((paragraph) => (
                  <p key={paragraph} className="text-sm leading-relaxed text-text-2">
                    {paragraph}
                  </p>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
