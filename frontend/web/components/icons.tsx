/**
 * The one deliberate piece of frontend "config" in the capability-menu
 * system (CLAUDE.md) — everything else about a menu item (label, route,
 * enabled, order) is backend-driven; icons stay a small, stable, code-side
 * lookup because they're a design asset, not something ops needs to tune.
 * Backend sends a stable string key (services/menu.py); this maps it to SVG.
 */
import type { SVGProps } from "react";

const icons: Record<string, (props: SVGProps<SVGSVGElement>) => React.ReactElement> = {
  mic: (props) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" {...props}>
      <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
      <path d="M19 10v2a7 7 0 01-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
    </svg>
  ),
  message: (props) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" />
    </svg>
  ),
  image: (props) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" {...props}>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" stroke="none" />
      <path d="M21 15l-5-5L5 21" />
    </svg>
  ),
  clone: (props) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" {...props}>
      <path d="M12 1a3 3 0 00-3 3v6a3 3 0 006 0V4a3 3 0 00-3-3z" />
      <path d="M17 8v2a5 5 0 01-10 0V8" />
      <line x1="12" y1="15" x2="12" y2="19" />
      <path d="M4 21c0-2.2 3.6-4 8-4s8 1.8 8 4" strokeDasharray="2.2 2.2" />
    </svg>
  ),
  wand: (props) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <path d="M15 4V2M15 16v-2M8 9h2M20 9h2M17.8 11.8L19 13M17.8 6.2L19 5M12.2 11.8L11 13M12.2 6.2L11 5" />
      <path d="M3 21l9-9" strokeLinecap="round" />
    </svg>
  ),
  video: (props) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" {...props}>
      <rect x="2" y="5" width="14" height="14" rx="2.5" />
      <path d="M16 9.5l5-3v11l-5-3z" />
    </svg>
  ),
  download: (props) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
      <polyline points="7,10 12,15 17,10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  ),
};

/** Unknown keys (e.g. an admin adds a capability before a matching icon
 * ships) fall back to this rather than crashing the sheet. */
const fallback = (props: SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
    <circle cx="12" cy="12" r="9" />
  </svg>
);

export function MenuIcon({ name, ...props }: { name: string } & SVGProps<SVGSVGElement>) {
  const Icon = icons[name] ?? fallback;
  return <Icon {...props} />;
}
