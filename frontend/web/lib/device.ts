/** Server-side only (reads a request header via `next/headers`) so the
 * `/get` landing page's primary CTA is right on the very first byte sent —
 * no client-side sniff-then-swap flash where the wrong button briefly
 * shows before flipping to the right one (ADR 0021). A `User-Agent`
 * substring check is the standard, good-enough way to detect Android;
 * false negatives (an Android browser with a scrubbed UA) just fall back
 * to the "web" default, never a broken page. */
export function isAndroidUserAgent(userAgent: string | null): boolean {
  return !!userAgent && /Android/i.test(userAgent);
}
