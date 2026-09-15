// Firebase client init (ADR 0008). Project ai-voice-labs-473713 is reused
// from the prior project on purpose — see CLAUDE.md. This file only reads
// NEXT_PUBLIC_* config, which is meant to be public (Firebase access is
// controlled by security rules, not by hiding this key).
import { type FirebaseApp, getApps, initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";
import { type Analytics, isSupported as analyticsIsSupported, getAnalytics } from "firebase/analytics";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

// Next.js can render this module on the server too (even for a "use client"
// page, the module graph gets evaluated there first) — guard against
// re-initializing across hot-reloads/multiple imports either way.
export const firebaseApp: FirebaseApp =
  getApps()[0] ?? initializeApp(firebaseConfig);

export const auth = getAuth(firebaseApp);
export const googleProvider = new GoogleAuthProvider();

// Firebase Analytics *is* GA4 under the hood (same Measurement ID, same
// Google Analytics reports) — reusing it means the marketing surface's
// analytics (ADR 0021) needs no second script/SDK alongside the Firebase
// one already loaded for auth. Lazy + async because `getAnalytics()`
// throws outside a browser (this module gets evaluated on the server too)
// and `isSupported()` itself is async (checks for IndexedDB, rules out
// some in-app/webview browsers) — callers await this instead of importing
// a top-level instance that would crash SSR. Returns null, never throws,
// when unsupported or `measurementId` isn't configured (empty in local
// dev unless `.env.local` sets it) — analytics being unavailable must
// never break the page it's measuring.
let analyticsPromise: Promise<Analytics | null> | null = null;

export function getFirebaseAnalytics(): Promise<Analytics | null> {
  if (typeof window === "undefined" || !firebaseConfig.measurementId) {
    return Promise.resolve(null);
  }
  if (!analyticsPromise) {
    analyticsPromise = analyticsIsSupported()
      .then((supported) => (supported ? getAnalytics(firebaseApp) : null))
      .catch(() => null);
  }
  return analyticsPromise;
}
