import Link from "next/link";

/** Honest about what's real: only "Job monitor" has a page behind it right
 * now. The rest of `routes_admin.py`'s surface (credit grants, capability
 * menu CRUD, Kie catalog CRUD, settings) is fully built and callable today
 * (`/docs`, curl) — just no screen yet, listed here so this dashboard
 * doesn't quietly hide what exists, per ADR 0020's scope note. */
const SECTIONS = [
  {
    href: "/admin/jobs",
    title: "Job monitor",
    description: "Last 100 jobs across every user.",
    enabled: true,
  },
  {
    href: null,
    title: "Users & credit grants",
    description: "GET/POST /admin/users/{id} — no screen yet, call the API directly.",
    enabled: false,
  },
  {
    href: null,
    title: "Capability menu",
    description: "GET/POST/PATCH/DELETE /admin/menu — no screen yet, call the API directly.",
    enabled: false,
  },
  {
    href: null,
    title: "Kie model catalog",
    description: "POST/PATCH/DELETE /admin/kie-models — no screen yet, call the API directly.",
    enabled: false,
  },
  {
    href: null,
    title: "Settings",
    description: "GET/PATCH /admin/settings/{key} — no screen yet, call the API directly.",
    enabled: false,
  },
];

export default function AdminDashboardPage() {
  return (
    <div>
      <h1 className="font-display text-2xl font-bold">Admin</h1>
      <p className="mt-1.5 text-sm text-text-2">
        Lives inside <code>frontend/web</code>, not a separate deployment (ADR 0020). Every
        section below is a plain consumer of <code>/admin/*</code>; enforcement happens
        server-side (<code>require_admin</code>), not here.
      </p>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {SECTIONS.map((section) =>
          section.enabled && section.href ? (
            <Link
              key={section.title}
              href={section.href}
              className="rounded-2xl border border-border-soft bg-surface p-5 transition-colors hover:border-a3/40"
            >
              <div className="font-display font-bold">{section.title}</div>
              <p className="mt-1.5 text-sm text-text-2">{section.description}</p>
            </Link>
          ) : (
            <div
              key={section.title}
              className="rounded-2xl border border-dashed border-border-soft p-5 opacity-60"
            >
              <div className="font-display font-bold">{section.title}</div>
              <p className="mt-1.5 text-sm text-text-2">{section.description}</p>
            </div>
          ),
        )}
      </div>
    </div>
  );
}
