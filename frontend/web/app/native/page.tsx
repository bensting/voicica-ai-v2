import { redirect } from "next/navigation";

/** The old project's Android WebView shell was built pointing at `/native`
 * as its home URL — a real, currently-live app on the Play Store (ADR
 * 0021's own finding: the installed app is the prior project's, not this
 * rewrite's still-unstarted native client). Now that `voicica.ai` serves
 * this rewrite instead, that hardcoded URL would 404 without this route.
 *
 * This isn't a real screen of its own — once this project's actual native
 * app (ADR 0005) exists, it won't need this indirection (a real app talks
 * to the backend API directly, not by loading a web URL in a WebView), so
 * this route only needs to keep existing as long as the old installed APK
 * does. `(app)/layout.tsx` already gates `/app` on Firebase auth state
 * client-side, so this only needs to forward — not duplicate — that check. */
export default function NativeShellRedirect() {
  redirect("/app");
}
