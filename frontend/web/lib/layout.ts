/** Shared page-content width, one breakpoint scale used by both the
 * `(app)` layout (the actual page content) and `BottomNav` (its own inner
 * row) — they have to stay in sync, or the nav visually stops lining up
 * with the content above it the moment a breakpoint kicks in.
 *
 * Phone width by default (`max-w-md`, matching this app's mobile-first
 * design — bottom nav, single-column pages); genuinely wider on a real
 * desktop viewport rather than just centering the same phone-width column
 * with empty space on both sides (a first pass that looked like a phone
 * stranded in the middle of a desktop browser, correctly called out —
 * "这样桌面端的客户就不用了吗？"). Content that benefits from the extra
 * room (Explore's thumbnail grids) gets it; a single-column form isn't
 * forced wider just because the shell is — its own page can still cap its
 * own width narrower inside this shell if it turns out too wide, on a
 * page-by-page basis, not solved globally here. */
export const APP_CONTENT_WIDTH = "max-w-md md:max-w-2xl lg:max-w-4xl";
